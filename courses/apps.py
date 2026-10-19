from django.apps import AppConfig


class CoursesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'courses'

    def ready(self):
        # Any change to catalogue data invalidates the career engine's shared cache.
        from django.db.models.signals import post_delete, post_save
        from clusters.models import Cluster
        from institutions.models import Institution
        from .catalogue import bump_version
        from .models import Course, CourseCategory, CourseOffering, CourseType
        for model in (Course, CourseOffering, CourseCategory, CourseType, Institution, Cluster):
            post_save.connect(bump_version, sender=model, dispatch_uid=f'catalogue_save_{model.__name__}')
            post_delete.connect(bump_version, sender=model, dispatch_uid=f'catalogue_delete_{model.__name__}')
