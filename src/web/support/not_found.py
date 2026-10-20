from .views import SupportPageView


def not_found(request, exception):
    """Use the approved recovery screen for real 404s without exposing exceptions."""
    view = SupportPageView(template_name="support/not_found.html")
    view.setup(request)
    return view.render_to_response(view.get_context_data(), status=404)
