from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse

from web.localization import translate_text
from web.seo.workspace import get_page, publish_page, restore_previous, save_draft

from .base_view import SeoWorkspaceView
from .errors import add_validation_error
from .page_form import SeoPageForm
from .selectors import page_schema


class SeoPageView(SeoWorkspaceView):
    template_name = "staff/seo/page.html"
    seo_section = "pages"
    http_method_names = ["get", "post", "head", "options"]

    def get_page(self):
        if self.kwargs["kind"] not in ("product", "category", "brand", "static"):
            raise Http404
        return get_page(self.kwargs["kind"], self.kwargs["key"], self.content_language())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = kwargs.get("seo_page") or self.get_page()
        form = kwargs.get("form") or SeoPageForm(user=self.request.user, page=page)
        fields = []
        for name in ("title", "description", "body"):
            fields.append({"name": name, "label": f"staff.seo.field.{name}",
                           "automatic": page["automatic"].get(name, ""),
                           "effective": page["effective"].get(name, ""),
                           "field": form[name] if name in form.fields else None,
                           "manual": bool(page.get(name))})
        preview = page["preview"]
        def may_publish(destination):
            if destination is None or not self.request.user.has_perm("seo.publish_seo"):
                return False
            return all(self.request.user.has_perm("seo.change_text" if name == "body" else "seo.change_metadata")
                       for name in ("title", "description", "body")
                       if destination.get(name, "") != page["published"].get(name, ""))
        context.update(seo_page=page, form=form, seo_fields=fields, preview=preview,
                       can_edit=any(name in form.fields for name in ("title", "body")),
                       can_publish=may_publish({name: page[name] for name in ("title", "description", "body")}),
                       can_restore=may_publish(page["previous"]),
                       technical_schema=page_schema(page, self.content_language()))
        return context

    def post(self, request, *args, **kwargs):
        page = self.get_page()
        form = SeoPageForm(request.POST, user=request.user, page=page)
        allowed = set(form.fields) - {"version"}
        if any(name in request.POST and name not in allowed for name in ("title", "description", "body")):
            raise PermissionDenied
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(seo_page=page, form=form), status=400)
        action = request.POST.get("action", "save")
        version = form.cleaned_data["version"]
        arguments = (request.user, kwargs["kind"], kwargs["key"], self.content_language())
        try:
            if action == "save":
                if not allowed:
                    raise PermissionDenied
                save_draft(*arguments, expected_version=version,
                           values={name: form.cleaned_data[name] for name in allowed})
            elif action.startswith("reset:"):
                field = action.removeprefix("reset:")
                if field not in allowed:
                    raise PermissionDenied
                save_draft(*arguments, expected_version=version, values={field: ""})
            elif action == "publish":
                if any(form.cleaned_data[name] != page.get(name, "") for name in allowed):
                    form.add_error(None, translate_text("staff.seo.save_first"))
                    return self.render_to_response(self.get_context_data(seo_page=page, form=form), status=409)
                publish_page(*arguments, expected_version=version)
            elif action == "restore":
                restore_previous(*arguments, expected_version=version)
            else:
                raise PermissionDenied
        except ValidationError as error:
            status = add_validation_error(form, error)
            return self.render_to_response(self.get_context_data(seo_page=page, form=form), status=status)
        messages.success(request, translate_text(f"staff.seo.saved.{action.split(':')[0]}"))
        return redirect(reverse("staff:seo_page", kwargs={"kind": kwargs["kind"], "key": kwargs["key"]})
                        + "?content_language=" + self.content_language())
