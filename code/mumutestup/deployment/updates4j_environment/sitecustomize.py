"""Scoped Maven environment fixes for Updates4J execution."""
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

_original_run = subprocess.run

def run_with_updates4j_environment(command, *args, **kwargs):
    if isinstance(command, (list, tuple)) and command and Path(str(command[0])).name == 'mvn':
        command = list(command)
        command.extend(['-Dspotless.check.skip=true', '-Dspotless.skip=true'])
        cwd = Path(kwargs.get('cwd') or os.getcwd())
        if 'install' in command:
            if 'klaw' in cwd.parts:
                command.append('-Dspring-boot.run.skip=true')
            if 'prebid-server-java' in cwd.parts:
                command.extend(['-DskipUnitTests=true', '-DskipITs=true'])
        if any('mutationCoverage' in str(part) for part in command):
            module = command[command.index('-pl') + 1] if '-pl' in command else '.'
            target = next((part.split('=', 1)[1] for part in command if str(part).startswith('-DtargetTests=')), '')
            test_file = cwd / module / 'src/test/java' / (target.replace('.', '/') + '.java')
            pom = cwd / module / 'pom.xml'
            if test_file.exists() and 'org.junit.jupiter' in test_file.read_text() and pom.exists():
                command = [part.replace('org.pitest:pitest-maven:1.9.11:', 'org.pitest:pitest-maven:1.15.2:') for part in command]
                tree = ET.parse(pom)
                root = tree.getroot()
                ns = '{http://maven.apache.org/POM/4.0.0}'
                def child(parent, name):
                    node = parent.find(ns + name)
                    return node if node is not None else ET.SubElement(parent, ns + name)
                plugins = child(child(root, 'build'), 'plugins')
                plugin = next((p for p in plugins if p.findtext(ns + 'artifactId') == 'pitest-maven'), None)
                if plugin is None:
                    plugin = ET.SubElement(plugins, ns + 'plugin')
                    child(plugin, 'groupId').text = 'org.pitest'
                    child(plugin, 'artifactId').text = 'pitest-maven'
                # Surefire can provide an engine implicitly; PIT needs it in the test classpath.
                junit_version = None
                for candidate in [pom, cwd / 'pom.xml']:
                    if candidate.exists():
                        candidate_root = ET.parse(candidate).getroot()
                        for dependency in candidate_root.findall('.//' + ns + 'dependency'):
                            if dependency.findtext(ns + 'artifactId') == 'junit-jupiter-api':
                                version = dependency.findtext(ns + 'version')
                                if version and not version.startswith('${'):
                                    junit_version = version
                if junit_version:
                    project_dependencies = child(root, 'dependencies')
                    if not any(d.findtext(ns + 'artifactId') == 'junit-jupiter-engine' for d in project_dependencies):
                        engine = ET.SubElement(project_dependencies, ns + 'dependency')
                        child(engine, 'groupId').text = 'org.junit.jupiter'
                        child(engine, 'artifactId').text = 'junit-jupiter-engine'
                        child(engine, 'version').text = junit_version
                        child(engine, 'scope').text = 'test'
                dependencies = child(plugin, 'dependencies')
                if not any(d.findtext(ns + 'artifactId') == 'pitest-junit5-plugin' for d in dependencies):
                    dependency = ET.SubElement(dependencies, ns + 'dependency')
                    child(dependency, 'groupId').text = 'org.pitest'
                    child(dependency, 'artifactId').text = 'pitest-junit5-plugin'
                    child(dependency, 'version').text = '1.2.2'
                ET.register_namespace('', ns[1:-1])
                tree.write(pom, encoding='UTF-8', xml_declaration=True)
        if 'openapi-generator' in cwd.parts:
            index = cwd.parts.index('openapi-generator')
            repository = Path(*cwd.parts[:index + 1])
            pom = repository / 'modules/openapi-generator/pom.xml'
            if pom.exists():
                tree = ET.parse(pom)
                root = tree.getroot()
                ns = '{http://maven.apache.org/POM/4.0.0}'
                def child(parent, name):
                    node = parent.find(ns + name)
                    return node if node is not None else ET.SubElement(parent, ns + name)
                plugins = child(child(root, 'build'), 'plugins')
                plugin = next((p for p in plugins if p.findtext(ns + 'artifactId') == 'jacoco-maven-plugin'), None)
                if plugin is None:
                    plugin = ET.SubElement(plugins, ns + 'plugin')
                    child(plugin, 'groupId').text = 'org.jacoco'
                    child(plugin, 'artifactId').text = 'jacoco-maven-plugin'
                excludes = child(child(plugin, 'configuration'), 'excludes')
                if not any(x.text == '**/*.jar' for x in excludes):
                    ET.SubElement(excludes, ns + 'exclude').text = '**/*.jar'
                ET.register_namespace('', ns[1:-1])
                tree.write(pom, encoding='UTF-8', xml_declaration=True)
        if 'prebid-server-java' in cwd.parts:
            index = cwd.parts.index('prebid-server-java')
            repository = Path(*cwd.parts[:index + 1])
            source = Path('/root/Baxxhy/work2/reproductions/testupdater/upstream/TestUpdater/repos/proto')
            target = repository / 'src/main/proto'
            target.mkdir(parents=True, exist_ok=True)
            for proto in source.glob('*.proto'):
                shutil.copy2(proto, target / proto.name)
    return _original_run(command, *args, **kwargs)

subprocess.run = run_with_updates4j_environment
