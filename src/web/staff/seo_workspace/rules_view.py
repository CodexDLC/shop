from django.contrib import messages
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse

from web.localization import translate_text
from web.seo.workspace import get_rule, preview_rule, publish_rule, restore_previous_rule, save_rule_draft

from .base_view import SeoWorkspaceView
from .errors import add_validation_error
from .rule_form import SeoRuleForm

PREVIEW_SALT = "staff.seo.rule-preview.v1"


class SeoRulesView(SeoWorkspaceView):
    template_name = "staff/seo/rules.html"
    seo_section = "rules"
    http_method_names = ["get", "post", "head", "options"]

    def kind(self):
        kind = self.request.GET.get("kind", "product")
        if kind not in ("product", "category", "brand", "static"):
            raise Http404
        return kind

    def preview_state(self, rule):
        return {"actor": self.request.user.pk, "kind": self.kind(), "language": self.content_language(),
                "version": rule["version"], "title_template": rule["title_template"],
                "description_template": rule["description_template"]}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rule = kwargs.get("rule") or get_rule(self.kind(), self.content_language())
        form = kwargs.get("form") or SeoRuleForm(rule=rule)
        examples = []
        try:
            examples = preview_rule(self.kind(), self.content_language(), {
                name: form[name].value() or "" for name in ("title_template", "description_template")}, limit=3)
        except ValidationError:
            if not form.errors:
                form.add_error(None, translate_text("staff.seo.invalid"))
        context.update(rule=rule, form=form, selected_kind=self.kind(), rule_examples=examples,
                       has_previous_rule=rule["previous"] is not None,
                       rule_preview_state=signing.dumps(self.preview_state(rule), salt=PREVIEW_SALT))
        return context

    def post(self, request, *args, **kwargs):
        if not request.user.has_perm("seo.manage_rules"):
            raise PermissionDenied
        rule = get_rule(self.kind(), self.content_language())
        form = SeoRuleForm(request.POST, rule=rule)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(rule=rule, form=form), status=400)
        action = request.POST.get("action", "save")
        values = {name: form.cleaned_data[name] for name in ("title_template", "description_template")}
        arguments = (request.user, self.kind(), self.content_language())
        try:
            if action == "preview":
                return self.render_to_response(self.get_context_data(rule=rule, form=form))
            if action == "save":
                save_rule_draft(*arguments, expected_version=form.cleaned_data["version"], values=values)
            elif action == "publish":
                try:
                    state = signing.loads(request.POST.get("preview_state", ""), salt=PREVIEW_SALT, max_age=3600)
                except signing.BadSignature:
                    state = None
                if any(values[name] != rule[name] for name in values):
                    form.add_error(None, translate_text("staff.seo.save_first"))
                    return self.render_to_response(self.get_context_data(rule=rule, form=form), status=409)
                if state != self.preview_state(rule) or not preview_rule(
                        self.kind(), self.content_language(), values, limit=3):
                    form.add_error(None, translate_text("staff.seo.preview_required"))
                    return self.render_to_response(self.get_context_data(rule=rule, form=form), status=409)
                # Publish only the saved, reviewed draft. Unsaved form values never enter publication.
                publish_rule(*arguments, expected_version=form.cleaned_data["version"])
            elif action == "restore":
                restore_previous_rule(*arguments, expected_version=form.cleaned_data["version"])
            else:
                raise PermissionDenied
        except ValidationError as error:
            status = add_validation_error(form, error)
            return self.render_to_response(self.get_context_data(rule=rule, form=form), status=status)
        messages.success(request, translate_text(f"staff.seo.saved.{action}"))
        return redirect(reverse("staff:seo_rules") + f"?kind={self.kind()}&content_language={self.content_language()}")
