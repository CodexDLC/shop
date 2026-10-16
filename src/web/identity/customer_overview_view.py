from web.customer.views import CustomerPageView


class CustomerOverviewView(CustomerPageView):
    template_name = "customer/overview.html"
