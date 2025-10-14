# Django app configuration for base_application module
# Docs: https://docs.djangoproject.com/en/stable/ref/applications/

from django.apps import AppConfig


# Defines configuration settings for the base_application app
class BaseApplicationConfig(AppConfig):
    # Use BigAutoField as default primary key type
    default_auto_field = 'django.db.models.BigAutoField'
    # Register the app under its internal Django name
    name = 'base_application'
