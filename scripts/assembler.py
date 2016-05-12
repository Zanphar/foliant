# -*- coding: utf-8 -*
import os
import sys
import json
import yaml
import datetime
import subprocess
import re
import fileinput
import shutil
import include_text as inc
import my_mail
import gitlab
import string
import glob
from time import gmtime, strftime

# TODO: Open all shell sessions via subprocess

git_url_prefix = "gitlab.com"
git_path = ""

reload(sys)
sys.setdefaultencoding('utf-8')

current_path = sys.argv[1]
user_input = sys.argv[2]
search_dir = os.path.join(current_path, 'sources')
fn = 'output.md'


def dir_list(dir_name, subdir, *args):
    fileList = []
    for file in os.listdir(dir_name):
        dirfile = os.path.join(dir_name, file)
        if os.path.isfile(dirfile):
            if len(args) == 0:
                fileList.append(dirfile)
            else:
                if os.path.splitext(dirfile)[1][1:] in args:
                    fileList.append(dirfile)
        elif os.path.isdir(dirfile) and subdir:
            fileList += dir_list(dirfile, subdir, *args)
    return fileList


def combine_files(fileList, fn):
    if not os.path.exists(os.path.join(current_path, 'scripts/staging')):
        os.makedirs(os.path.join(current_path, 'scripts/staging'))
    output = open(os.path.join(os.path.join(current_path, 'scripts/staging'), fn), 'w')
    with open(os.path.join(current_path, "main.yaml"), 'r') as main:
        contents = yaml.load(main)

        def recursive_handle(chapter):
            for name in chapter:
                chapter_content = chapter[name]
                for section in chapter_content:
                    if isinstance(section, dict):
                        combine(''.join(section.keys()))
                        recursive_handle(section)
                    elif isinstance(section, str):
                        if section.startswith('git:'):
                            section = section[4:]
                        combine(section)

        def yaml_to_oneline_list(node):
            oneline_list = []
            if isinstance(node, basestring):
                oneline_list.append(node)
            elif isinstance(node, list):
                for val in node:
                    oneline_list.extend(yaml_to_oneline_list(val))
            elif isinstance(node, dict):
                for key, val in node.iteritems():
                    oneline_list.append(key)
                    oneline_list.extend(yaml_to_oneline_list(val))
            else:
                print "! %s" % type(node)

            return oneline_list

        f = open(current_path + '/main.yaml', 'r')
        d = yaml.load(f)
        f.close()
        yaml_list = yaml_to_oneline_list(d)

        def combine(section):
            for file in fileList:
                # TODO: hash table instead of iteration
                # TODO: combine files with same names but located in different directories
                source_name, source_ext = os.path.splitext(os.path.basename(file))
                if source_name == section:
                    print section
                    output.write(open(file).read().decode('utf-8') + '\n' + '\n')

        def chapter_from_git(contents):
            git_pattern = re.compile("git:(?P<file_name>.*)")
            for chapter in contents['chapters']:
                found = git_pattern.match(chapter)
                if found:
                    if not os.path.exists(os.path.join(current_path, 'sources')):
                        os.makedirs(os.path.join(current_path, 'sources'))
                    file_name = found.group('file_name') + '.md'
                    c = open('config.json')
                    config = json.load(c)
                    c.close()
                    git_project = config['git_project']
                    if '/' in git_project:
                        git_project = git_project.replace('/', '%2F')
                    git_branch = config['git_branch']
                    git_private_token = config['git_private_token']

                    git = gitlab.Gitlab(git_url_prefix, token=git_private_token)
                    str_from_git = git.getrawfile(git_project, git_branch, file_name)

                    f = open(current_path + '/sources/' + file_name, 'w')
                    f.write(str(str_from_git))
                    f.close()

                    shutil.copy(current_path + '/sources/' + file_name, current_path + '/scripts/staging')

                    pic_pattern = re.compile('!\[.*[^\]]\]\((?P<pic_name>.*[^\)])\)')

                    found_pic = pic_pattern.findall(str_from_git)
                    for pic in found_pic:
                        git_path = pic
                        image = git.getfile(git_project, git_path, git_branch)
                        content = image['content']
                        img = open(current_path + '/sources/graphics/' + pic, 'wb')
                        img.write(content.decode('base64'))
                        img.close()
                        shutil.copy(current_path + '/sources/graphics' + pic, current_path + '/scripts/staging')
                    return True

        try:
            del_check = chapter_from_git(contents)
        except:
            print 'No chapters from git in input files'

    fileList = dir_list(search_dir, True, 'md')
    recursive_handle(contents)
    output.close()
    main.close()
    return del_check


def config_handler():
    config_data = open(os.path.join(current_path, 'scripts/config.json'))
    config = json.load(config_data)
    config_data.close()
    send_to_pandoc = dict()

    variable_string = ""

    for key in config:
        # TODO: Remove strict naming
        if key == "git_project":
            continue
        elif key == "git_private_token":
            continue
        elif key == "git_branch":
            continue
        elif key == "lang":
            if config[key] == "russian":
                send_to_pandoc["russian"] = "true"
            if config[key] == "english":
                send_to_pandoc["english"] = "true"
        elif key == "title_page":
            if config[key].lower() in ['true', '1']:
                send_to_pandoc[key] = "true"
        elif key == "toc":
            if config[key].lower() in ['true', '1']:
                send_to_pandoc[key] = "true"
        elif key == "tof":
            if config[key].lower() in ['true', '1']:
                send_to_pandoc[key] = "true"
        elif key == "type":
            if config[key].lower() not in ['none', '']:
                send_to_pandoc[key] = config[key]
        elif key == "alt_doc_type":
            if config[key].lower() not in ['none', '']:
                send_to_pandoc[key] = config[key]
        elif key == "version":
            if config[key].strip().lower() == 'auto':
                send_to_pandoc[key] = get_version_counter()
            elif config[key].lower() not in ['none', '']:
                send_to_pandoc[key] = config[key]
        elif key == "second_title":
            if config[key].lower() not in ['none', '']:
                send_to_pandoc[key] = config[key]
        elif key == "date":
            if config[key].lower() in ['true', '1']:
                send_to_pandoc[key] = "true"
        elif key == "template":
            template = config[key]
        elif key == "title":
            final_file = config[key].replace(" ", "_")
            send_to_pandoc[key] = config[key]
        else:
            send_to_pandoc[key] = config[key]

    for key in send_to_pandoc:
        variable_string = "--variable {0}=\"{1}\" {2}".format(key, send_to_pandoc[key], variable_string).strip()
    return variable_string, template, final_file


def replace_text(file, search_exp, replace_exp):
    for line in fileinput.input(file, inplace=1):
        if search_exp in line:
            line = line.replace(search_exp, replace_exp)
        sys.stdout.write(line)


def replace_text_re(file, search_exp, replace_exp):
    for line in fileinput.input(file, inplace=1):
        line = re.sub(search_exp, r'{0}'.format(replace_exp), line)
        sys.stdout.write(line)


def latex_preprocessor(output_file):
    replace_text_re(output_file, '<!-- Latex: (.*) -->', '\\1')


def docx_preprocessor(output_file):
    replace_text(output_file, '.eps', '.png')
    replace_text_re(output_file, '<!-- DOCX: (.*) -->', '\\1')
    replace_text(output_file, '\\begin{mdframed}[style=redbar]', '')
    replace_text(output_file, '\\end{mdframed}', '')


def run_pandoc(file_type, variable_string, template):
    # TODO: Bilatex references handling
    output_file = os.path.join(os.path.join(current_path, 'scripts/staging'), fn)
    if file_type == "p":
        latex_preprocessor(output_file)
        pandoc_launch = "cd {0}/scripts/staging; pandoc -o output.pdf -f markdown_strict+simple_tables+multiline_tables+grid_tables+pipe_tables+table_captions+fenced_code_blocks+line_blocks+definition_lists+all_symbols_escapable+strikeout+superscript+subscript+lists_without_preceding_blankline+implicit_figures+raw_tex+citations+tex_math_dollars+header_attributes+auto_identifiers+startnum+footnotes+inline_notes+fenced_code_attributes+intraword_underscores+yaml_metadata_block -t latex --template={0}/scripts/template/{2}.tex --no-tex-ligatures --smart --normalize --latex-engine=xelatex {1} output.md;".format(
            current_path, variable_string, template)
        os.popen(pandoc_launch)
    elif file_type == "d":
        convert_images = 'echo "Converting images..."; find {0}/scripts/staging -iname "*.eps" -exec mogrify -format png -transparent white -density 200 {1} +;'.format(
            current_path, '{}')
        os.popen(convert_images)
        docx_preprocessor(output_file)
        pandoc_launch = 'cd {0}/scripts/staging; pandoc -o output.docx -f markdown_strict+simple_tables+multiline_tables+grid_tables+pipe_tables+table_captions+fenced_code_blocks+line_blocks+definition_lists+all_symbols_escapable+strikeout+superscript+subscript+lists_without_preceding_blankline+implicit_figures+raw_tex+citations+tex_math_dollars+header_attributes+auto_identifiers+startnum+footnotes+inline_notes+fenced_code_attributes+intraword_underscores+yaml_metadata_block --template={0}/scripts/template/{2}.tex --no-tex-ligatures --smart --normalize --listings --latex-engine=xelatex --reference-docx={0}/scripts/ref.docx --toc --toc-depth=4 {1} output.md;'.format(
            current_path, variable_string, template)
        os.popen(pandoc_launch)
        add_docx_title()
    elif file_type == "g":
        convert_images = 'echo "Converting images..."; find {0}/scripts/staging -iname "*.eps" -exec mogrify -format png -transparent white -density 200 {1} +;'.format(
            current_path, '{}')
        os.popen(convert_images)
        version_counter = get_version_counter()
        with open(output_file, 'r') as original:
            data = original.read()
        with open(output_file, 'w') as modified:
            modified.write('_Version of the document: ' + version_counter + '.' + datetime.date.today().strftime(
                '%d-%m-%Y') + data)
        original.close()
        modified.close()
        docx_preprocessor(output_file)
        pandoc_launch = "cd {0}/scripts/staging; pandoc -o output.docx -f markdown_strict+simple_tables+multiline_tables+grid_tables+pipe_tables+table_captions+fenced_code_blocks+line_blocks+definition_lists+all_symbols_escapable+strikeout+superscript+subscript+lists_without_preceding_blankline+implicit_figures+raw_tex+citations+tex_math_dollars+header_attributes+auto_identifiers+startnum+footnotes+inline_notes+fenced_code_attributes+yaml_metadata_block --template={0}/scripts/template/{2}.tex --no-tex-ligatures --smart --normalize --latex-engine=xelatex --reference-docx={0}/scripts/ref-simple.docx {1} output.md;".format(
            current_path, variable_string, template)
        os.popen(pandoc_launch)
    elif file_type == "t":
        latex_preprocessor(output_file)
        pandoc_launch = "cd {0}/scripts/staging; pandoc -o output.tex -f markdown_strict+simple_tables+multiline_tables+grid_tables+pipe_tables+table_captions+fenced_code_blocks+line_blocks+definition_lists+all_symbols_escapable+strikeout+superscript+subscript+lists_without_preceding_blankline+implicit_figures+raw_tex+citations+tex_math_dollars+header_attributes+auto_identifiers+startnum+footnotes+inline_notes+fenced_code_attributes+yaml_metadata_block -t latex --template={0}/scripts/template/{2}.tex --no-tex-ligatures --smart --normalize --listings --latex-engine=xelatex {1} output.md;".format(
            current_path, variable_string, template)
        os.popen(pandoc_launch)


def get_version_counter():
    cmd_version_counter_first = "cd {0}; git describe --abbrev=0".format(current_path)
    cmd_version_counter_second = "cd {0}; git rev-list --count master".format(current_path)

    def cmd_process(value):
        process = subprocess.Popen(value, stdout=subprocess.PIPE, stderr=None, shell=True).communicate()[0].replace(
            "\n", "")
        return process

    def version_counter_first():
        git_message = cmd_process(cmd_version_counter_first)
        if git_message == '':
            return '0'
        else:
            return ''.join(c for c in git_message if c.isdigit())

    def version_counter_second():
        return cmd_process(cmd_version_counter_second)

    return version_counter_first() + '.' + version_counter_second()


def move_output_file(file_type, file_title, version_counter):
    if file_type == 'p':
        file_extension = 'pdf'
    if (file_type == 'd') or (file_type == 'd'):
        file_extension = 'docx'
    if file_type == 't':
        file_extension = 'tex'
    if file_type == 'm':
        file_extension = 'md'
    file_title = (file_title + '_' + version_counter + '-' + strftime("%d-%m-%Y", gmtime()))

    stage_folder = '{0}/scripts/staging'.format(current_path)
    old_file = '{0}/scripts/staging/output.{1}'.format(current_path, file_extension)
    new_file = '{0}/{1}.{2}'.format(current_path, file_title, file_extension)
    os.rename(old_file, new_file)
    shutil.rmtree(stage_folder)
    return file_title + '.' + file_extension


def add_docx_title():
    def copy_to_stage(file_name):
        scripts_path = '{0}/scripts/{1}'.format(current_path, file_name)
        stage_path = '{0}/scripts/staging/{1}'.format(current_path, file_name)
        shutil.copyfile(scripts_path, stage_path)

    copy_to_stage('atitle.docx')
    copy_to_stage('add_title.applescript')
    applescript_launch = "cd {0}/scripts/staging; osascript add_title.applescript".format(current_path)
    os.popen(applescript_launch)

    # TODO: Automatic seqdiag generation
    # TODO: pipeline of handlers
    # TODO: regexps for smooth typography
    # TODO: regexps for trailing spaces
    # TODO: drag out latex specific handlers like  \begin and \end
