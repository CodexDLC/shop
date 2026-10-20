from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="DeletionReceipt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("notification_id", models.CharField(max_length=200, unique=True)),
                ("topic", models.CharField(max_length=64)),
                ("schema_version", models.CharField(max_length=20)),
                ("event_date", models.DateTimeField()),
                ("received_at", models.DateTimeField(auto_now_add=True)),
                ("payload_fingerprint", models.CharField(max_length=64)),
                ("user_fingerprint", models.CharField(max_length=64)),
                ("status", models.CharField(default="review_required", editable=False, max_length=32)),
            ],
            options={"ordering": ("received_at",)},
        ),
    ]
