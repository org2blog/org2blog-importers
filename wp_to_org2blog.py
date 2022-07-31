#!/usr/bin/env python

"""wp_to_org2blog.py: Convert wordpress.xml to org2blog posts.

To create and export of Posts and nothing else:

- Log in to your WordPress site
- Dashboard, Tools, Export
- Posts
  - Categories: All
  - Authors: All
  - Date range start, end: "Start Date", "End Date"
    - Returns every post
  - Status: All
- Direct download and add.

"""

__author__ = "Puneeth Chaganti"
__copyright__ = "Copyright 2011"
__license__ = "GPLv3"
__version__ = "0.7"
__email__ = "punchagan@muse-amuse.in"


import os
import re
import argparse
import logging


from time import strptime, strftime
from xml.dom import minidom
from subprocess import Popen, PIPE, SubprocessError
from shlex import split
from urllib.parse import unquote

SUBTREE_TEMPLATE = u"""\
%(stars)s %(title)s %(tags)s
%(space)s :PROPERTIES:
%(space)s :POSTID: %(id)s
%(space)s :POST_DATE: %(date)s
%(space)s :CATEGORY: %(categories)s
%(space)s :END:

%(space)s %(text)s

"""

BUFFER_TEMPLATE = u"""\
#+POSTID: %(id)s
#+DATE: %(date)s
#+OPTIONS: toc:nil num:nil todo:nil pri:nil tags:nil ^:nil TeX:nil
#+CATEGORY: %(categories)s
#+TAGS: %(tags)s
#+TITLE: %(title)s

%(text)s


"""

def html_to_org(html):
    """Converts a html snippet to an org-snippet."""

    command = 'pandoc -r html -t org --wrap=none -'
    args = split(command)

    proc = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, error = proc.communicate(html)

    if (proc.returncode != 0) or (error is not None):
        errormessage = """%s exited with return code %s and error %s when parsing:
            %s"""
        raise SubprocessError(
             errormessage % (args[0], proc.returncode, error, html)
        )

    return output

def get_first_child_data(node, tag_name):
    """Try to retrieve the data contained at a node's tag's firstChild."""
    try:
        return node.getElementsByTagName(tag_name)[0].firstChild.data
    except (AttributeError, IndexError):
        return None

def node_to_post(node):
    """Takes an XML node from the export and converts it to a dict"""

    # key: (XML) tag_name
    key_map = {
        'title': 'title',
        'link': 'link',
        'date': 'pubDate',
        'author': 'dc:creator',
        'id': 'wp:post_id',
        'text': 'content:encoded',
        'post_name': 'wp:post_name'
    }
    post = dict()

    for key, tag_name in key_map.items():
        post[key] = get_first_child_data(node, tag_name)

    try:
        if int(post['id']) % 10 == 0:
            logging.getLogger().info("Processing post #%s", post['id'])
    except ValueError:
        logging.getLogger().debug("Processing post #%s", post['id'])

    if post['text'] is not None:
        post['text'] = post['text'].replace('\r\n', '\n')
        post['text'] = post['text'].replace('\n', '#$NEWLINE-MARKER$#')
        post['text'] = html_to_org(post['text'].encode('utf8')).decode('utf8')
        post['text'] = post['text'].replace('#$NEWLINE-MARKER$#', '\n')
    else:
        post['text'] = ''

    # Get the tags and categories
    post['tags'] = list()
    post['categories'] = list()

    for element in node.getElementsByTagName('category'):
        domain, name = element.getAttribute('domain'), element.getAttribute('nicename')

        if name and domain and ('tag' in domain or 'category' in domain):
            name = element.firstChild.data
            domain = 'tags' if 'tag' in domain else 'categories'
            post[domain].append(name)

    return post

def xml_to_list(infile):
    """Return a list containing all the posts from the infile.
    Each post is a dictionary.
    """

    dom = minidom.parse(infile)

    blog = list() # list that will contain all posts

    for node in dom.getElementsByTagName('item'):

        post = node_to_post( node )

        for domain in ['tags', 'categories']:
            post[domain] = sorted(set(post[domain]))

        # FIXME - wp:attachment_url could be use to download attachments

        blog.append(post)

    return blog

def link_to_file(link, post_name=None):
    """Gets filename from wordpress url."""

    name = None
    check_for_letters = re.compile('[a-z]+', re.IGNORECASE)
    try:
        if (post_name != "") and (post_name is not None):
            if check_for_letters.match(post_name) is not None:
                name = post_name
            else:
                name = None

        if name is None:
            if "?p=" in link:
                name = link.split('?p=')[-1]
            else:
                name = link.split('/')[-2]

        name = '%s.org' % unquote(name)
    # occasionally, some encoding errors may seep through
    except TypeError:
        logging.getLogger().debug("Error getting file link for %s, %s", link, post_name)

    return name

def parse_date(date, date_format):
    """Change wp date format to a different format."""

    if date is not None:
        date = date.split('+')[0].strip()
        date = strptime(date, '%a, %d %b %Y %H:%M:%S')
        date = strftime(date_format, date)

        return date

def blog_to_org(blog_list, name, level, separate_buffer, prefix):
    """Converts a blog-list into an org file."""

    space = ' ' * level
    stars = '*' * level

    tag_sep = ', '
    cat_sep = ', '

    template_parts = dict()

    if separate_buffer:
        template = BUFFER_TEMPLATE
    else:
        template = SUBTREE_TEMPLATE
        tag_sep = ':'
        org_file = open('%s.org' % name, 'wb')

    for post in blog_list:
        post['tags'] = tag_sep.join(post['tags'])
        if tag_sep == ':':
            post['tags'] = ':' + post['tags'] + ':'
        post['categories'] = cat_sep.join(post['categories'])
        date_wp_fmt = post['date']
        post['date'] = parse_date(date_wp_fmt, '[%Y-%m-%d %a %H:%M]')

        if not separate_buffer:
            post['text'] = post['text'].replace('\n', '\n %s' % space)

        template_parts.update(**post)
        template_parts.update(space=space)
        template_parts.update(stars=stars)
        post_output = template % template_parts

        if separate_buffer:
            if prefix:
                file_name = "%s-%s" % (parse_date(date_wp_fmt, '%Y-%m-%d'),
                                       link_to_file(post['link'], post['post_name']))
            else:
                file_name = link_to_file(post['link'], post['post_name'])
            if not os.path.exists(name):
                os.mkdir(name)
            else:
                org_file = open(os.path.join(name, file_name), 'wb')
                org_file.write(post_output.encode('utf8'))
                org_file.close()
        else:
            org_file.write(post_output.encode('utf8'))

    org_file.close()

def main():
    parser = argparse.ArgumentParser(
        description='Convert wordpress.xml to org2blog posts.')

    parser.add_argument('in_file', help='the input xml file exported from WP')
    parser.add_argument('--buffer', action='store_true',
                        help='enable to obtain a separate file for each post')
    parser.add_argument('--prefix-date', action='store_true',
                        help='prefix a date to the post files, when --buffer')
    parser.add_argument('-l', '--level', type=int, default=1,
                        help='level of the subtree when exporting to SUBTREE')
    parser.add_argument('-o', '--out-file', default='org-posts',
                        help='file or directory name for output')

    args = parser.parse_args()

    logging_format = '%(message)s'
    logging.basicConfig(format=logging_format, level=logging.INFO)
    logger = logging.getLogger()


    logger.warning("Parsing xml ...")
    blog_list = xml_to_list(args.in_file)

    logger.warning("Writing posts...")
    blog_to_org(blog_list, args.out_file, args.level, args.buffer,
                args.prefix_date)

    logger.warning("Done!")


if __name__ == "__main__":
    main()

