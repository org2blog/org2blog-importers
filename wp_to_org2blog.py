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

    p = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, error = p.communicate(html)

    if (p.returncode != 0) or (error is not None):
        errormessage = """%s exited with return code %s and error %s when parsing:
            %s"""
        raise SubprocessError(
             errormessage % (args[0], p.returncode, error, html)
        )

    return output

def get_firstChild_data(node, element):
    """Try to retrieve the data contained at a node's firstChild element."""
    try:
        return node.getElementsByTagName(element)[0].firstChild.data
    except (AttributeError, IndexError):
        return None

def node_to_post(node):
    """Takes an XML node from the export and converts it to a dict"""
    key_map = {
        'title': 'title',
        'link': 'link',
        'date': 'pubDate',
        'author': 'dc:creator',
        'id': 'wp:post_id',
        'text': 'content:encoded'
    }
    post = dict()

    for key, el in key_map.items():
        post[key] = get_firstChild_data(node, el)

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
    post['tags'], post['categories'] = [], []

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

    blog = [] # list that will contain all posts

    for node in dom.getElementsByTagName('item'):
        post = dict()

        post = node_to_post( node )

        for domain in ['tags', 'categories']:
            post[domain] = sorted(set(post[domain]))

        # FIXME - wp:attachment_url could be use to download attachments

        blog.append(post)

    return blog

def link_to_file(link):
    """Gets filename from wordpress url."""
    name = link.split('/')[-2]
    name = '%s.org' % unquote(name)
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

    tag_sep = cat_sep = ', '

    if separate_buffer:
        template = BUFFER_TEMPLATE
    else:
        template = SUBTREE_TEMPLATE
        tag_sep = ':'
        f = open('%s.org' % name, 'w')

    for post in blog_list:
        post['tags'] = tag_sep.join(post['tags'])
        if tag_sep == ':':
            post['tags'] = ':' + post['tags'] + ':'
        post['categories'] = cat_sep.join(post['categories'])
        date_wp_fmt = post['date']
        post['date'] = parse_date(date_wp_fmt, '[%Y-%m-%d %a %H:%M]')

        if not separate_buffer:
            post['text'] = post['text'].replace('\n', '\n %s' % space)

        post_output = template % dict(post, **{'space': space, 'stars': stars})

        if separate_buffer:
            if prefix:
                file_name = "%s-%s" % (parse_date(date_wp_fmt, '%Y-%m-%d'),
                                       link_to_file(post['link']))
            else:
                file_name = link_to_file(post['link'])
            if not os.path.exists(name):
                os.mkdir(name)
            else:
                f = open(os.path.join(name, file_name), 'w')
                f.write(post_output.encode('utf8'))
                f.close()
        else:
            f.write(post_output.encode('utf8'))

    f.close()

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

    FORMAT = '%(message)s'
    logging.basicConfig(format=FORMAT, level=logging.INFO)
    logger = logging.getLogger()


    logger.warning("Parsing xml ...")
    blog_list = xml_to_list(args.in_file)

    logger.warning("Writing posts...")
    blog_to_org(blog_list, args.out_file, args.level, args.buffer,
                args.prefix_date)

    logger.warning("Done!")


if __name__ == "__main__":
    main()
