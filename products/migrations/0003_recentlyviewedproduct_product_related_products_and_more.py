
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_product_product_image'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RecentlyViewedProduct',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('viewed_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-viewed_at'],
            },
        ),
        migrations.AddField(
            model_name='product',
            name='related_products',
            field=models.ManyToManyField(blank=True, help_text='Products that are accessories or frequently bought with this item.', related_name='accessory_for', to='products.product'),
        ),
        migrations.AlterField(
            model_name='product',
            name='sku',
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['is_active', 'category'], name='products_pr_is_acti_1cd666_idx'),
        ),
        migrations.AddIndex(
            model_name='product',
            index=models.Index(fields=['is_active', 'featured'], name='products_pr_is_acti_9fd782_idx'),
        ),
        migrations.AddField(
            model_name='recentlyviewedproduct',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='products.product'),
        ),
        migrations.AddField(
            model_name='recentlyviewedproduct',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recently_viewed', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='recentlyviewedproduct',
            unique_together={('user', 'product')},
        ),
    ]
