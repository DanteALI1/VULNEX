from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vulns", "0003_alter_vulnerability_vendor_and_product_name_textfield"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vulnerability",
            name="title",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="vulnerability",
            name="vuln_status",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="vulnerability",
            name="exploit_present",
            field=models.TextField(blank=True, default=""),
        ),
    ]
