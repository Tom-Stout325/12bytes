This patch brings the MoneyPro-style core foundation into 12bytes in a way
that is safe before the accounts app is migrated.

Included:
- core/models.py
- core/mixins.py
- core/admin.py
- core/forms.py
- core/middleware.py
- core/views.py
- core/urls.py
- core/apps.py
- core/migrations/0001_initial.py
- templates/core/business_onboarding.html

Notes:
- Middleware redirects to core:onboarding for now, not accounts:onboarding.
- CompanyProfile completeness checks are intentionally not included yet.
- BusinessFeature remains in core for future module access control.
