"""Composition root: one store and synchronous application services per lifespan."""
import logging
from app.core.storage import create_store, StorageUnavailable
from app.core.idempotency import Idempotency
from app.core.rate_limit import RateLimiter
from app.modules.identity.service import Identity
from app.modules.catalog.service import Catalog
from app.modules.catalog.bootstrap import seed_bank, seed_demo
from app.modules.recommendations.service import Recommendations
from app.modules.experiences.service import Experiences
from app.modules.content_jobs import ContentJobs
from app.modules.activity_assistant.service import ActivityAssistant

logger = logging.getLogger('uvicorn.error')


class Services:
    def __init__(self, settings, clock, store_factory=None):
        self.settings, self.clock = settings, clock
        logger.info('API startup: checking MongoDB connection, replica-set primary, indexes and transactions')
        try:
            self.store = (store_factory or create_store)({'DATA_BACKEND': settings.data_backend,
                                                         'MONGODB_URI': settings.mongodb_uri})
        except StorageUnavailable as exc:
            # StorageUnavailable messages are explicitly credential-free.
            logger.error('API startup: %s', exc)
            raise
        try:
            logger.info('API startup: MongoDB checks passed; initializing application services')
            self._initialize()
        except BaseException:
            self.store.close()
            raise

    def _initialize(self):
        settings, clock = self.settings, self.clock
        self.limiter = RateLimiter(self.store, clock)
        self.identity = Identity(self.store, settings, clock, self.limiter)
        self.catalog = Catalog(self.store, clock)
        self.recommendations = Recommendations(self.store, self.catalog, self.identity, clock)
        self.experiences = Experiences(self.store, self.catalog, self.recommendations, self.identity, clock)
        self.idempotency = Idempotency(self.store, clock)
        logger.info('API startup: importing owner seeds without overwriting existing content')
        seed_bank(self.store, clock)
        if settings.demo_content:
            logger.info('API startup: loading the configured authored catalog')
            if settings.catalog_release == 'legacy':
                seed_demo(self.store, clock)
            elif settings.catalog_release == 'real700':
                from app.modules.catalog.curated import import_catalog
                from app.modules.catalog.northern_outings import import_northern_outings
                from app.modules.catalog.practical_now import import_practical_now
                import_catalog(self.store, clock)
                import_practical_now(self.store, clock)
                import_northern_outings(self.store, clock)
            else:
                from app.modules.catalog.import_unified import import_unified
                import_unified(self.store, clock)
        logger.info('API startup: preparing the in-process content runner')
        self.jobs = ContentJobs(self.store, self.catalog, settings, clock)
        self.activity_assistant = ActivityAssistant(self.store, self.catalog, self.limiter, settings, clock)
