import tempfile
import os
import sqlite3
import re
from shutil import rmtree, copytree

from django.core.management.base import BaseCommand
from django.core.urlresolvers import reverse
from django.http import HttpRequest
from sphinx.ext.intersphinx import fetch_inventory

from bs4 import BeautifulSoup

from cbv.models import Klass, ProjectVersion
from cbv.views import VersionDetailView, ModuleDetailView, KlassDetailView


class Command(BaseCommand):
    args = ''
    help = 'Generates the Dash Docsets'
    # versions of Django which are supported by CCBV
    django_versions = ProjectVersion.objects.all()

    def fix_html(self, content, level=1):
        """ Fixes relative paths in the HTML, removes navbar, fixes static files """

        # fix relative paths
        content = content.replace('/projects/Django/1.7/', '')
        content = re.sub(r'href="(?!http)', 'href="%s' % (''.join(['../']*level)), content)

        # fix static files
        content = content.replace('https://None.s3.amazonaws.com', ''.join(['../'] * level) + 'static')

        soup = BeautifulSoup(content)

        # remove navbar
        [nav.extract() for nav in soup.findAll('div', {'class': 'navbar'})]

        # build the table of contents
        for method in soup.findAll('div', {'class': 'accordion-body'}):
            anchor = soup.new_tag('a')
            anchor['name'] = '//apple_ref/cpp/Method/%s' % method['id']
            anchor['class'] = 'dashAnchor'
            method.insert_before(anchor)

        content = soup.prettify()

        return content

    def handle(self, *args, **options):
        work_dir = os.path.join(tempfile.gettempdir(), 'django-dash')
        rmtree(work_dir, ignore_errors=True)
        os.mkdir(work_dir)

        fake_request = HttpRequest()
        fake_request.method = 'GET'

        for version in self.django_versions:
            # Version detail
            version_dir_base = os.path.join(work_dir, 'Django-CBV-%s.docset' % version.version_number)
            version_dir = os.path.join(version_dir_base, 'Contents', 'Resources', 'Documents')
            os.makedirs(version_dir)

            copytree(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..', '..', 'cbv', 'static'), os.path.join(version_dir, 'static'))

            # Generate plist file
            with open(os.path.join(version_dir_base, 'Contents', 'Info.plist'), 'w') as f:
                f.write('''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleIdentifier</key>
    <string>django-%s-cbv</string>
    <key>CFBundleName</key>
    <string>Django %s CBV</string>
    <key>DocSetPlatformFamily</key>
    <string>django-cbv</string>
    <key>isDashDocset</key>
    <true/>
    <key>DashDocSetFamily</key>
    <string>dashtoc</string>
    <key>isJavaScriptEnabled</key>
    <true/>
</dict>
</plist>''' % (version.version_number, version.version_number))

            database = sqlite3.connect(os.path.join(version_dir_base, 'Contents', 'Resources', 'docSet.dsidx'))
            cursor = database.cursor()

            cursor.execute('CREATE TABLE searchIndex(id INTEGER PRIMARY KEY, name TEXT, type TEXT, path TEXT);')
            cursor.execute('CREATE UNIQUE INDEX anchor ON searchIndex (name, type, path);')

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
                    f.write(self.fix_html(content.content))

                cursor.execute('INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES (?, "Module", ?);', (module.name, os.path.join(module.name, 'index.html')))

                for klass in module.klass_set.all():
                    # Klass/Class detail
                    klass_dir = os.path.join(module_dir, klass.name)
                    os.mkdir(klass_dir)

                    kwargs['klass'] = klass.name
                    url = reverse('klass-detail', kwargs=kwargs)
                    content = KlassDetailView.as_view()(fake_request, **kwargs)
                    content.render()

                    with open(os.path.join(klass_dir, 'index.html'), 'w') as f:
                        f.write(self.fix_html(content.content, level=2))

                    cursor.execute('INSERT OR IGNORE INTO searchIndex(name, type, path) VALUES (?, "Class", ?);', (klass.name, os.path.join(module.name, klass.name, 'index.html')))

                    del kwargs['klass']

            database.commit()
            database.close()