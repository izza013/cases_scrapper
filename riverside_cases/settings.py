BOT_NAME = "riverside_cases"

SPIDER_MODULES = ["riverside_cases.spiders"]
NEWSPIDER_MODULE = "riverside_cases.spiders"


ROBOTSTXT_OBEY = True


USER_AGENT = "riverside_cases_bot/1.0 (+https://your-email-or-site.example)"


CONCURRENT_REQUESTS = 4
DOWNLOAD_DELAY = 1.0


ITEM_PIPELINES = {
    "riverside_cases.pipelines.CaseCleaningPipeline": 300,
}


AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0
