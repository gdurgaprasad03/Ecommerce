# Generated migration to fix SKU unique constraint
# This allows multiple NULL/empty SKU values while enforcing uniqueness on non-null values

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_product_products_pr_is_acti_973eb8_idx_and_more'),
    ]

    operations = [
        # Step 1: Remove the old unique constraint on SKU field
        migrations.AlterField(
            model_name='product',
            name='sku',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        
        # Step 2: Add new conditional unique constraint (only for non-null SKUs)
        migrations.AddConstraint(
            model_name='product',
            constraint=models.UniqueConstraint(
                condition=models.Q(('sku__isnull', False)),
                fields=['sku'],
                name='products_product_sku_unique_nonnull'
            ),
        ),
        
        # Step 3: Clean up existing data - convert empty strings to NULL
        # This is safe because empty SKUs can now have duplicates
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model('products', 'Product').objects.filter(sku='').update(sku=None),
            reverse_code=lambda apps, schema_editor: None,  # No need to reverse
        ),
    ]
