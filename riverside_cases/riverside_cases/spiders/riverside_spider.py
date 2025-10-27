import scrapy
import re
from scrapy.http import FormRequest
import requests
from PIL import Image
from io import BytesIO
import cv2
import numpy as np
import urllib3
import easyocr
import os
import traceback
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class RiversideSpider(scrapy.Spider):
    name = "riverside"
    start_urls = ["https://epublic-access.riverside.courts.ca.gov/public-portal/?q=user/login"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.logger.info("Initializing EasyOCR")
        self.reader = easyocr.Reader(['en'], gpu=False)  # Set gpu=True if you have CUDA
        self.logger.info("EasyOCR initialized successfully")

    def preprocess_captcha_image(self, image):
        
     
        img_array = np.array(image)
        
        
        if len(img_array.shape) == 3:
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = img_array
        
        
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        
        denoised = cv2.fastNlMeansDenoising(binary, None, 10, 7, 21)
        
    
        height, width = denoised.shape
        resized = cv2.resize(denoised, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)
        
        return resized

    def solve_image_captcha(self, captcha_url):
        try:
            self.logger.info(f"Downloading CAPTCHA image: {captcha_url}")
            
            
            response = requests.get(captcha_url, timeout=10, verify=False)
            response.raise_for_status()
            
            # Open image
            image = Image.open(BytesIO(response.content))
            
            
            img_array = np.array(image)
            
            
            self.logger.info("Attempting OCR on original image")
            result = self.reader.readtext(img_array, detail=0, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
            
            if result and len(result) > 0:
                captcha_text = ''.join(result).strip().replace(" ", "")
                self.logger.info(f"Solved CAPTCHA : '{captcha_text}'")
                return captcha_text
            
          
            self.logger.info("Original image failed trying preprocessed image")
            processed_img = self.preprocess_captcha_image(image)
            cv2.imwrite("captcha_processed.png", processed_img)
            
            result = self.reader.readtext(processed_img, detail=0, allowlist='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789')
            
            if result and len(result) > 0:
                captcha_text = ''.join(result).strip().replace(" ", "")
                self.logger.info(f"Solved CAPTCHA : '{captcha_text}'")
                return captcha_text
            
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error solving CAPTCHA: {e}")
            
            self.logger.error(traceback.format_exc())
            return None


    def parse(self, response):
        

        
        captcha_src = response.xpath("//img[contains(@src, 'image_captcha')]/@src").get()
        
        if captcha_src:
            captcha_url = response.urljoin(captcha_src)
            self.logger.info(f"Found CAPTCHA URL: {captcha_url}")
            
            
            captcha_value = self.solve_image_captcha(captcha_url)
            
            if not captcha_value:
                
                captcha_value = input(f"Open {captcha_url} in your browser and enter CAPTCHA: ")
        else:
            self.logger.warning("No CAPTCHA found on page")
            captcha_value = ""

       
        form_build_id = response.xpath("//input[@name='form_build_id']/@value").get()
        captcha_sid = response.xpath("//input[@name='captcha_sid']/@value").get()
        captcha_token = response.xpath("//input[@name='captcha_token']/@value").get()

        formdata = {
            "name": "jj9696778@gmail.com",
            "pass": "!NewSetup99#",
            "form_build_id": form_build_id,
            "form_id": "user_login",
            "captcha_sid": captcha_sid,
            "captcha_token": captcha_token,
            "captcha_response": captcha_value,
            "op": "Log in",
        }

        yield FormRequest.from_response(
            response,
            formdata=formdata,
            callback=self.after_login,
            meta={"captcha_url": captcha_url if captcha_src else None, "retry_count": 0}
        )

    

    def after_login(self, response):
        if "Logout" in response.text or "Log out" in response.text:
            self.logger.info("Logged in successfully")
            yield scrapy.Request(
                "https://epublic-access.riverside.courts.ca.gov/public-portal/?q=node/379",
                callback=self.search_case
            )
        else:
            
            retry_count = response.meta.get("retry_count", 0)
            
            if retry_count < 3 and "CAPTCHA" in response.text:
                self.logger.warning(f"Login CAPTCHA incorrect, retrying ({retry_count+1}/3)...")
                yield scrapy.Request(
                    self.start_urls[0],
                    callback=self.parse,
                    dont_filter=True,
                    meta={"retry_count": retry_count + 1}
                )
            else:
                
                with open("login_failed.html", "wb") as f:
                    f.write(response.body)

    

   
    def search_case(self, response):
        case_number = "PRMC2400654"
        self.logger.info(f"Searching for case: {case_number}")

        

        
        captcha_label = response.xpath('//label[contains(text(), "Math question")]//text()').getall()
        captcha_text = " ".join(captcha_label).strip()
        
      
        if not re.search(r"\d+\s*[+\-*/xX]", captcha_text):
            captcha_text_alt = response.xpath('//label[contains(text(), "Math question")]/following::text()[1]').get()
            if captcha_text_alt:
                captcha_text = captcha_text + " " + captcha_text_alt.strip()
        
        if not re.search(r"\d+\s*[+\-*/xX]", captcha_text):
            captcha_container = response.xpath('//label[contains(text(), "Math question")]/parent::*//text()').getall()
            captcha_text = " ".join([t.strip() for t in captcha_container if t.strip()])
        
        if not re.search(r"\d+\s*[+\-*/xX]", captcha_text):
            captcha_full = response.xpath('//div[contains(@class, "form-item")]//label[contains(text(), "Math question")]/..//text()').getall()
            captcha_text = " ".join([t.strip() for t in captcha_full if t.strip()])
        
        self.logger.info(f"Raw CAPTCHA label text: {captcha_text}")

        
        match = re.search(r"(\d+)\s*([+\-*/xX])\s*(\d+)", captcha_text)
        if not match:
            all_text = " ".join(response.xpath('//text()').getall())
            math_section = re.search(r"Math question[^=]*?(\d+)\s*([+\-*/xX×÷])\s*(\d+)\s*=", all_text, re.IGNORECASE)
            if math_section:
                match = math_section
                self.logger.info(f"Found math question using aggressive search")
            else:
                self.logger.error("Could not extract math question from CAPTCHA.")
        
                
                return

        a, op, b = match.groups()
        a, b = int(a), int(b)
        
       
        if op in ['*', 'x', 'X']:
            math_answer = a * b
        elif op == '+':
            math_answer = a + b
        elif op == '-':
            math_answer = a - b
        elif op == '/':
            math_answer = int(a / b)
        
        self.logger.info(f"Solved CAPTCHA: {a} {op} {b} = {math_answer}")

    
        form_build_id = response.xpath("//input[@name='form_build_id']/@value").get()
        form_token = response.xpath("//input[@name='form_token']/@value").get()
        form_id = response.xpath("//input[@name='form_id']/@value").get()
        
       
        case_field_name = response.xpath("//input[@type='text' and @maxlength='50']/@name").get()
        if not case_field_name:
            case_field_name = response.xpath("//label[contains(text(), 'Case Number')]/following-sibling::input/@name").get()
        
        if not case_field_name:
            case_field_name = "data(147057)"
        
        self.logger.info(f"Case field name: {case_field_name}")

        formdata = {
            case_field_name: case_number,
            "captcha_response": str(math_answer),
            "op": "Search"
        }
        
        if form_build_id:
            formdata["form_build_id"] = form_build_id
        if form_token:
            formdata["form_token"] = form_token
        if form_id:
            formdata["form_id"] = form_id

        

        yield FormRequest.from_response(
            response,
            formdata=formdata,
            callback=self.parse_search_results,
            dont_filter=True,
            meta={"retry_count": 0, "case_number": case_number}
        )


 
    def retry_search(self, response):
        retry_count = response.meta.get("retry_count", 0)
        if retry_count >= 3:
            self.logger.error("CAPTCHA failed too many times")
            with open("retry_failed.html", "wb") as f:
                f.write(response.body)
            return

        self.logger.warning(f"CAPTCHA incorrect, retrying ({retry_count+1}/3)...")
        yield scrapy.Request(
            "https://epublic-access.riverside.courts.ca.gov/public-portal/?q=node/379",
            callback=self.search_case,
            dont_filter=True,
            meta={"retry_count": retry_count + 1}
        )

   

    def parse_search_results(self, response):
        if "The answer you entered for the CAPTCHA" in response.text or "incorrect" in response.text.lower():
            self.logger.warning("CAPTCHA was incorrect")
            yield from self.retry_search(response)
            return

        case_link = response.xpath("//a[contains(@href, 'node/385')]/@href").get()
        
        if not case_link:
            case_link = response.xpath("//a[contains(text(), 'PRMC')]/@href").get()
        
        if not case_link:
            case_link = response.xpath("//td[@class='views-field views-field-php-2']//a/@href").get()

        if case_link:
            url = response.urljoin(case_link)
            self.logger.info(f"Found case details link: {url}")
            yield scrapy.Request(url, callback=self.parse_case_details)
        else:
            self.logger.warning("No case found — saving response for debugging")
           
            
            self.logger.info("Available links on page:")
            for link in response.xpath("//a/@href").getall()[:10]:
                self.logger.info(f"  - {link}")



    def parse_case_details(self, response):
        """Extract raw data from case details page"""
        
      
        self.logger.info("Saved case details page for debugging")

        
        case_number = response.xpath("//td[@style='color: #CC0000; font-size:18px;']/b/text()").get()
        if not case_number:
            case_number = response.xpath("//td/b[contains(text(), 'PRMC')]/text()").get()
        if case_number:
            case_number = case_number.strip()
        
        # Extract filed date
        filed_date = response.xpath("//td[contains(text(),'Filed Date')]/following-sibling::td[@style='text-align:left;font-weight:bold;padding-left:5px;']/text()").get()
        if not filed_date:
            filed_date = response.xpath("//td[contains(text(),'Filed Date')]/following-sibling::td/text()").get()
        if filed_date:
            filed_date = filed_date.strip()
        
        # Extract case type
        case_type = response.xpath("//td[@style='text-align: center; overflow-wrap: normal;']/b/text()").get()
        if not case_type:
            case_type = response.xpath("//td[contains(text(),'Case Type')]/following-sibling::td/text()").get()
        if case_type:
            case_type = case_type.strip()
        
        
        case_status = response.xpath("//td[contains(text(),'Status')]/following-sibling::td[@style='text-align:left;font-weight:bold;padding-left:5px;']/text()").get()
        if not case_status:
            case_status = response.xpath("//td[contains(text(),'Status')]/following-sibling::td/text()").get()
        if case_status:
            case_status = case_status.strip()
        
        # Extract description
        description = response.xpath("//td[@style='text-align: center; font-size:18px;']/text()").get()
        if description:
            description = description.strip()
        
       
        parties = []
        party_name_cells = response.xpath("//td[starts-with(@id, 'tree_table-') and contains(@id, '-cell-1')]")
        
        self.logger.info(f"Found {len(party_name_cells)} party name cells")
        
        for cell in party_name_cells:
            all_text = cell.xpath(".//text()").getall()
            party_name = None
            for text in reversed(all_text):
                cleaned = text.strip()
                if cleaned and cleaned != "&nbsp;":
                    party_name = cleaned
                    break
            
            if party_name:
                party_type_cell = cell.xpath("./following-sibling::td[1]")
                if party_type_cell:
                    party_type_text = party_type_cell.xpath(".//text()").getall()
                    party_type = None
                    for text in party_type_text:
                        cleaned = text.strip()
                        if cleaned:
                            party_type = cleaned
                            break
                    
                    if party_type:
                        self.logger.info(f"Found party: {party_name} - {party_type}")
                        parties.append({
                            "name": party_name,
                            "type": party_type
                        })
        
       
        if not parties:
            self.logger.info("Using fallback method for party extraction")
            party_type_cells = response.xpath("//td[contains(text(), 'Decedent') or contains(text(), 'Administrator') or contains(text(), 'Petitioner') or contains(text(), 'Executor') or contains(text(), 'JUDGE')]")
            
            for type_cell in party_type_cells:
                party_type = type_cell.xpath("./text()").get()
                if party_type:
                    party_type = party_type.strip()
                
                name_cell = type_cell.xpath("./preceding-sibling::td[1]")
                if name_cell:
                    name_text = name_cell.xpath(".//text()").getall()
                    party_name = None
                    for text in reversed(name_text):
                        cleaned = text.strip()
                        if cleaned and cleaned != "&nbsp;":
                            party_name = cleaned
                            break
                    
                    if party_name and party_type:
                        self.logger.info(f"✓ Found party (fallback): {party_name} - {party_type}")
                        parties.append({
                            "name": party_name,
                            "type": party_type
                        })

        
        item = {
            "case_number": case_number,
            "filed_date": filed_date,
            "case_type": case_type,
            "status": case_status,
            "description": description,
            "parties": parties
        }

        self.logger.info(f"Extracted raw case: {item['case_number']}")
        
        yield item
