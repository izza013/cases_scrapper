import scrapy

class CaseItem(scrapy.Item):
    case_number = scrapy.Field()
    filed_date = scrapy.Field()
    case_type = scrapy.Field()
    status = scrapy.Field()
    description = scrapy.Field()
    parties = scrapy.Field()
