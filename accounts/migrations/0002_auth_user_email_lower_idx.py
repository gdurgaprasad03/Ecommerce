"""
Functional index on LOWER(auth_user.email) so case-insensitive email lookups
(used on every login and registration) are O(log n) instead of a full scan.

CREATE INDEX CONCURRENTLY runs without taking an ACCESS EXCLUSIVE lock,
so it is safe to run against a live production database. It cannot run
inside a transaction, hence atomic = False.
"""
from django.db import migrations


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ("accounts", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
                "auth_user_email_lower_idx ON auth_user (LOWER(email));"
            ),
            reverse_sql=(
                "DROP INDEX CONCURRENTLY IF EXISTS auth_user_email_lower_idx;"
            ),
        ),
    ]
