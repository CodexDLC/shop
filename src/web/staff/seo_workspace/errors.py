from web.localization import translate_text


def add_validation_error(form, error):
    codes = [item.code for item in error.error_list] if hasattr(error, "error_list") else []
    stale = "stale" in codes
    form.add_error(None, translate_text("staff.seo.stale" if stale else "staff.seo.invalid"))
    return 409 if stale else 400
