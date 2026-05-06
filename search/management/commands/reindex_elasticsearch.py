"""
Django management command to reindex all products in Elasticsearch
Usage: python manage.py reindex_elasticsearch
"""

from django.core.management.base import BaseCommand
from search.search import ElasticsearchSearchManager
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Reindex all products in Elasticsearch'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Perform a full reindex (delete and recreate index)',
        )

    def handle(self, *args, **options):
        try:
            self.stdout.write(self.style.SUCCESS('Starting Elasticsearch reindexing...'))

            if options['full']:
                self.stdout.write('Performing full reindex (deleting and recreating index)...')
                success = ElasticsearchSearchManager.reindex_all()
            else:
                self.stdout.write('Performing incremental reindex...')
                from products.models import Product

                products = Product.objects.filter(is_active=True)
                count = 0

                for product in products:
                    ElasticsearchSearchManager.index_product(product)
                    count += 1

                if count > 0:
                    self.stdout.write(self.style.SUCCESS(f'Successfully indexed {count} products'))
                success = True

            if success:
                self.stdout.write(self.style.SUCCESS('Elasticsearch reindexing completed successfully!'))
            else:
                self.stdout.write(self.style.ERROR('Elasticsearch reindexing failed!'))

        except Exception as e:
            logger.error(f"Error during Elasticsearch reindexing: {str(e)}")
            self.stdout.write(self.style.ERROR(f'Error: {str(e)}'))
