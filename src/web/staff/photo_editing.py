from django.core.exceptions import ValidationError

from web.catalog.models import ProductImage
from web.localization.translation import translate_text


def save_photo(product, image, values, created_files):
    """Caller holds product lock and atomic block; created_files supports rollback cleanup."""
    images = list(product.images.order_by("position", "pk"))
    if image is None and len(images) >= 100:
        raise ValidationError(translate_text("staff.photos.limit"))
    old_color = image.color_code if image else None
    image = image or ProductImage(product=product)
    image.color_code = values["color_code"]
    image.alt_text = values["alt_text"]
    upload = values.get("upload")
    if upload:
        image.file.save(upload.name, upload, save=False)
        created_files.append((image.file.storage, image.file.name))
    # Reserve unused valid smallint positions, then normalize both affected galleries.
    # This avoids transient uniqueness conflicts when moving/swapping images.
    affected = {old_color, image.color_code}
    groups = {color: [item for item in images if item.color_code == color and item.pk != image.pk]
              for color in affected if color is not None}
    target = groups[image.color_code]
    target.insert(min(values["position"], len(target)), image)
    for color, members in groups.items():
        occupied = {item.position for item in images if item.color_code == color}
        spare = (value for value in range(32767, -1, -1) if value not in occupied)
        for member in members:
            member.position = next(spare)
            if member is image:
                member.save()
            else:
                ProductImage.objects.filter(pk=member.pk, product=product).update(position=member.position)
    # Move every affected row (including the image changing colour) to spare
    # positions before filling final positions in either gallery. The old
    # gallery may otherwise try to reuse position zero while the moved image
    # still occupies it; set iteration order must not decide whether it saves.
    for members in groups.values():
        for position, member in enumerate(members):
            ProductImage.objects.filter(pk=member.pk, product=product).update(position=position)
    return image


def delete_photo(image):
    # Intentionally retain old physical files: transactions/backups may still reference them.
    # A future audited storage reconciliation job can remove verified unreferenced objects.
    image.delete()
