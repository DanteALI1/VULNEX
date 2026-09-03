from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vulns", "0002_vulnerability_bdu_raw_vulnerability_exploit_present_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vulnerability",
            name="title",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="vulnerability",
            name="vendor",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AlterField(
            model_name="vulnerability",
            name="product_name",
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
