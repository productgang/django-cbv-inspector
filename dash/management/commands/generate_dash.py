import tempfile
import os
from shutil import rmtree

from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from django.http import HttpRequest
from sphinx.ext.intersphinx import fetch_inventory

from cbv.models import Klass, ProjectVersion
from cbv.views import VersionDetailView, ModuleDetailView, KlassDetailView


class Command(BaseCommand):
    args = ''
    help = 'Generates the Dash Docsets'
    # versions of Django which are supported by CCBV
    django_versions = ProjectVersion.objects.all()

    def handle(self, *args, **options):
        work_dir = os.path.join(tempfile.gettempdir(), 'django-dash')
        rmtree(work_dir, ignore_errors=True)
        os.mkdir(work_dir)

        print work_dir
        

        fake_request = HttpRequest()
        fake_request.method = 'GET'

        for version in self.django_versions:
            # Version detail
            version_dir = os.path.join(work_dir, version.version_number)
            os.mkdir(version_dir)

            kwargs = {'package': 'Django', 'version': version.version_number}
            url = reverse('version-detail', kwargs=kwargs)
            content = VersionDetailView.as_view()(fake_request, **kwargs)
            content.render()

            with open(os.path.join(version_dir, 'index.html'), 'w') as f:
                f.write(content.content)

            for module in version.module_set.all():
                # Module detail
                module_dir = os.path.join(version_dir, module.name)
                os.mkdir(module_dir)

                kwargs['module'] = module.name
                url = reverse('module-detail', kwargs=kwargs)
                content = ModuleDetailView.as_view()(fake_request, **kwargs)
                content.render()

                with open(os.path.join(module_dir, 'index.html'), 'w') as f:
                    f.write(content.content)

                for klass in module.klass_set.all():
                    # Klass/Class detail
                    klass_dir = os.path.join(module_dir, klass.name)
                    os.mkdir(klass_dir)

                    kwargs['klass'] = klass.name
                    url = reverse('klass-detail', kwargs=kwargs)
                    content = KlassDetailView.as_view()(fake_request, **kwargs)
                    content.render()

                    with open(os.path.join(klass_dir, 'index.html'), 'w') as f:
                        f.write(content.content)

                    del kwargs['klass']