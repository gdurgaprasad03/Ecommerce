
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0005_product_products_pr_is_acti_973eb8_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='sku',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        
        migrations.AddConstraint(
            model_name='product',
            constraint=models.UniqueConstraint(
                condition=models.Q(('sku__isnull', False)),
                fields=['sku'],
                name='products_product_sku_unique_nonnull'
            ),
        ),
        
        migrations.RunPython(
            code=lambda apps, schema_editor: apps.get_model('products', 'Product').objects.filter(sku='').update(sku=None),
            reverse_code=lambda apps, schema_editor: None,
        ),
    ]
