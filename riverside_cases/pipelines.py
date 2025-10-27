import re
from datetime import datetime

def to_title_case(s: str) -> str:
    if not s:
        return s
    
    s = s.strip()
    
    return " ".join(word.capitalize() if word.isupper() or word.islower() else word for word in s.split())

def normalize_date(date_str: str) -> str:
    """
    Expecting a date like 06/26/2024 or MM/DD/YYYY or similar.
    Return YYYY-MM-DD or original if parse fails.
    """
    if not date_str:
        return ""
    date_str = date_str.strip()
 
    for fmt in ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
 
    m = re.search(r"(\d{1,2})[^\d](\d{1,2})[^\d](\d{4})", date_str)
    if m:
        mm, dd, yy = m.groups()
        try:
            dt = datetime(int(yy), int(mm), int(dd))
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    return date_str 

class CaseCleaningPipeline:
    def process_item(self, item, spider):
        
        item['case_number'] = item.get('case_number', '').strip()

        
        item['filed_date'] = normalize_date(item.get('filed_date', ''))

       
        item['case_type'] = to_title_case(item.get('case_type', ''))
        item['status'] = to_title_case(item.get('status', ''))
        item['description'] = to_title_case(item.get('description', ''))

        
        parties = item.get('parties') or []
        cleaned_parties = []
        for p in parties:
            name = p.get('name', '').strip()
            ptype = p.get('type', '').strip()
            
            if not name:
                continue
            
            if 'judge' in name.lower() or 'judge' in ptype.lower():
                continue
            cleaned_parties.append({
                'name': to_title_case(name),
                'type': to_title_case(ptype)
            })
        item['parties'] = cleaned_parties

        return item
