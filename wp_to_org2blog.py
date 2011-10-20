#!/usr/bin/env python

"""wp_to_org2blog.py: Convert wordpress.xml to org2blog posts."""

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
from subprocess import Popen, PIPE
from shlex import split
from urllib2 import unquote

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
    command = 'pandoc -r html -t org --no-wrap -'
    args = split(command)
    p = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    output, error = p.communicate(html)
    if not error:
        return output
    else:
        raise Exception(error)

def xml_to_list(infile):
    """Return a list containing all the posts from the infile.
    Each post is a dictionary.
    """

    dom = minidom.parse(infile)

    blog = [] # list that will contain all posts

    for node in dom.getElementsByTagName('item'):
        post = dict()

        post['title'] = node.getElementsByTagName('title')[0].firstChild.data
        post['link'] = node.getElementsByTagName('link')[0].firstChild.data
        post['date'] = node.getElementsByTagName('pubDate')[0].firstChild.data
        post['author'] = node.getElementsByTagName(
            'dc:creator')[0].firstChild.data
        post['id'] = node.getElementsByTagName('wp:post_id')[0].firstChild.data

        if node.getElementsByTagName('content:encoded')[0].firstChild != None:
            post['text'] = node.getElementsByTagName(
                'content:encoded')[0].firstChild.data
            post['text'] = post['text'].replace('\r\n', '\n')
            post['text'] = post['text'].replace('\n', '#$NEWLINE-MARKER$#')
            post['text'] = html_to_org(post['text'].encode('utf8')).decode('utf8')
            post['text'] = post['text'].replace('#$NEWLINE-MARKER$#', '\n')
        else:
            post['text'] = ''

        # Get the tags and categories
        post['tags'], post['categories'] = [], []

        for element in node.getElementsByTagName('category'):
            domain, name = element.getAttribute('domain'), \
                           element.getAttribute('nicename')
            if name and domain and ('tag' in domain or 'category' in domain):
                name = element.firstChild.data
                domain = 'tags' if 'tag' in domain else 'categories'
                post[domain].append(name)

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

def parse_date(date, format):
    """Change wp date format to a different format."""
    date = date.split('+')[0].strip()
    date = strptime(date, '%a, %d %b %Y %H:%M:%S')
    date = strftime(format, date)
    return date

def blog_to_org(blog_list, name, level, buffer, prefix):
    """Converts a blog-list into an org file."""

    space = ' ' * level
    stars = '*' * level

    tag_sep = cat_sep = ', '

    if buffer:
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

        if not buffer:
            post['text'] = post['text'].replace('\n', '\n %s' % space)

        post_output = template % dict(post, **{'space': space, 'stars': stars})

        if buffer:
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

if __name__ == "__main__":

    import argparse
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
    logging.basicConfig(format=FORMAT)
    logger = logging.getLogger()


    logger.warning("Parsing xml ...")
    blog_list = xml_to_list(args.in_file)

    logger.warning("Writing posts...")
    blog_to_org(blog_list, args.out_file, args.level, args.buffer,
                args.prefix_date)

    logger.warning("Done!")
