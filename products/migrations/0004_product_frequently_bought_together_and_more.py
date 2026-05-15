
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_recentlyviewedproduct_product_related_products_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='frequently_bought_together',
            field=models.ManyToManyField(blank=True, help_text='Products that are frequently bought together with this item.', related_name='bought_with', to='products.product'),
        ),
        migrations.AlterField(
            model_name='product',
            name='related_products',
            field=models.ManyToManyField(blank=True, help_text='Products that are accessories for this item (e.g. Bag, Mouse for a Laptop).', related_name='accessory_for', to='products.product'),
        ),
    ]
