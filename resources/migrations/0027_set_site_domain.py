from django.db import migrations

DOMAIN = 'www.careernext.co.ke'


def set_domain(apps, schema_editor):
    # The sitemap and allauth emails build absolute URLs from the Site row; Django ships it as example.com.
    Site = apps.get_model('sites', 'Site')
    Site.objects.filter(pk=1, domain='example.com').update(domain=DOMAIN, name='CareerNext')


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0026_seed_paste_help_video'),
        ('sites', '0002_alter_domain_unique'),
    ]

    operations = [
        migrations.RunPython(set_domain, migrations.RunPython.noop),
    ]
