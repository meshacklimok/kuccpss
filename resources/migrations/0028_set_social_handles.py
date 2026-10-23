from django.db import migrations

HANDLE = "meshacklimok"


def set_handles(apps, schema_editor):
    SiteSetting = apps.get_model("resources", "SiteSetting")
    for key in ("twitter_handle", "instagram_handle"):
        SiteSetting.objects.filter(key=key).update(value=HANDLE)


class Migration(migrations.Migration):
    dependencies = [("resources", "0027_set_site_domain")]
    operations = [migrations.RunPython(set_handles, migrations.RunPython.noop)]
