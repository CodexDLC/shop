from django.shortcuts import render

from .safe_view import OAuthSafeView


class ResultView(OAuthSafeView):
    def get(self, request):
        message = ("Autorisierung abgeschlossen. Sie können dieses Fenster schließen."
                   if request.GET.get("status") == "connected" else
                   "Keine Verbindung gespeichert. Bitte den Einladungslink erneut öffnen und das richtige Konto wählen.")
        return render(request, "ebay_oauth/message.html", {"message": message})
