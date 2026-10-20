from time import time

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache

from web.localization import translate_text

from .forms import ContactForm
from .models import ContactTicket
from .views import SupportPageView


@method_decorator(never_cache, name="dispatch")
class ContactCreateView(SupportPageView):
    http_method_names = ["post"]

    def post(self, request):
        try:
            length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            length = 20001
        if length < 0 or length > 20000:
            return HttpResponse(translate_text("support.help.ui.contact_limit"), status=413)
        mobile = request.POST.get("form_source") == "mobile"
        self.template_name = "support/help_mobile.html" if mobile else "support/help.html"
        form = ContactForm(request.POST)
        now = time()
        raw_attempts = request.session.get("contact_attempts", [])
        attempts = [stamp for stamp in raw_attempts[-5:] if isinstance(stamp, (int, float))
                    and now - 3600 < stamp <= now] if isinstance(raw_attempts, list) else []
        if len(attempts) >= 5:
            form.is_valid()
            form.add_error(None, translate_text("support.help.ui.contact_limit"))
            return self.render_to_response(self.get_context_data(contact_form=form), status=429)
        request.session["contact_attempts"] = [*attempts, now]
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(contact_form=form), status=400)
        data = form.cleaned_data
        ContactTicket.objects.create(
            user=request.user if request.user.is_authenticated else None,
            **{key: data[key] for key in ("name", "email", "topic", "message")},
        )
        messages.success(request, translate_text("support.help.ui.contact_saved"), extra_tags="contact-saved")
        target = "support:help_mobile" if mobile else "support:help"
        return redirect(reverse(target) + "#kontakt-formular")
