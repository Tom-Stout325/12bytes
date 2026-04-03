from .models import CompanyProfile


def company_context(request):
    business = getattr(request, "business", None)
    company_profile = None
    if business is not None:
        try:
            company_profile = business.company_profile
        except CompanyProfile.DoesNotExist:
            company_profile = None
    return {
        "active_business": business,
        "company_profile": company_profile,
    }
