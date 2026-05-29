from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0006_fix_sku_unique_constraint"),
    ]

    operations = [
        # Enables the pg_trgm extension used by the trigram GIN indexes below.
        # Requires the DB role to have privileges to CREATE EXTENSION.
        TrigramExtension(),
        migrations.AddIndex(
            model_name="product",
            index=GinIndex(
                fields=["name"],
                name="product_name_trgm_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ),
        migrations.AddIndex(
            model_name="product",
            index=GinIndex(
                fields=["description"],
                name="product_desc_trgm_idx",
                opclasses=["gin_trgm_ops"],
            ),
        ),
    ]
