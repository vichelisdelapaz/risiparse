#!/usr/bin/python3

from typing import List, Optional
import sqlite3
import re
import pathlib
import logging

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "risiparse.db"


def _replace_page_number(page_link: str) -> str:
    """
    The link stored in the database has a variable page number
    so we replace the the page number in the link by % to match
    the link.
    """
    page_link_number = [
              m.span() for m in re.finditer(r"\d*\d", page_link)
    ]
    page_link = (
              page_link[:page_link_number[3][0]]
              + '%'
    )
    return page_link


def create_db() -> None:
    con = sqlite3.connect(DB_PATH)
    try:
        with con:
            con.execute(
                '''create table if not exists risitas
                (id integer primary key autoincrement,
                domain varchar,
                title varchar,
                page_link varchar,
                file_path varchar,
                total_pages integer,
                current_page integer,
                message_cursor integer)'''
            )
            con.execute(
                '''create table if not exists authors
                (id integer primary key autoincrement,
                name varchar,
                risitas_id integer,
                foreign key(risitas_id) references risitas(id))'''
            )
    except sqlite3.OperationalError as e:
        logging.exception(e)
    con.close()


def read_db(page_link: str) -> List[Optional[tuple]]:
    create_db()
    con = sqlite3.connect(DB_PATH)
    page_link_normalized = _replace_page_number(page_link)
    try:
        with con:
            cursor = con.execute(
                '''select * from risitas where page_link LIKE ? limit 1''',
                (page_link_normalized, )
            )
            risitas_row = cursor.fetchone()
            rows = [risitas_row]
            if risitas_row:
                cursor_author = con.execute(
                    '''select name from authors where risitas_id = ?''',
                    (risitas_row[0], )
                )
                authors_row = cursor_author.fetchall()
                rows.append(authors_row)
    except sqlite3.OperationalError as e:
        logging.exception(e)
    con.close()
    return rows


def update_db(
        domain: str,
        title: str,
        page_link: str,
        file_path: 'pathlib.Path',
        total_pages: int,
        current_page: int,
        message_cursor: int,
        authors: List,
) -> None:
    create_db()
    # Need to handle the updates of existing rows
    file_path_str = str(file_path)
    con = sqlite3.connect(DB_PATH)
    page_link_normalized = _replace_page_number(page_link)
    cursor_existing_row = con.execute(
        '''select id from risitas where page_link like ? limit 1''',
        (page_link_normalized, )
    ).fetchone()
    if cursor_existing_row:
        try:
            with con:
                cursor = con.execute(
                    '''UPDATE risitas
                    SET domain = ?,
                    title = ?,
                    page_link = ?,
                    file_path = ?,
                    total_pages = ?,
                    current_page = ?,
                    message_cursor = ?
                    WHERE id = ?''',
                    (
                        domain,
                        title,
                        page_link,
                        file_path_str,
                        total_pages,
                        current_page,
                        message_cursor,
                        cursor_existing_row[0],
                    )
                )
                logging.info(
                    "A risitas has been updated in the database!"
                )
                logging.debug(
                    f"Id: {id} "
                    f"Title: {title} "
                    f"Current page: {current_page} "
                    f"Total pages : {total_pages}"
                )
                cursor_existing_row = con.execute(
                    '''select name from authors where id = ?''',
                    (cursor_existing_row[0], )
                ).fetchall()
                stored_authors = [author[0] for author in cursor_existing_row]
                for author in authors:
                    if author not in stored_authors:
                        con.execute(
                            '''INSERT INTO authors
                            (name, risitas_id)
                            VALUES (?, ?)''',
                            (
                                author,
                                cursor_existing_row[0],
                            )
                        )
                        logging.debug(
                            f"Author : {author} "
                            "has been inserted in the database!"
                        )
        except sqlite3.OperationalError as e:
            logging.exception(e)
    else:
        try:
            with con:
                cursor = con.execute(
                    '''INSERT INTO risitas
                    (domain,
                    title,
                    page_link,
                    file_path,
                    total_pages,
                    current_page,
                    message_cursor)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''',
                    (
                        domain,
                        title,
                        page_link,
                        file_path_str,
                        total_pages,
                        current_page,
                        message_cursor,
                    )
                )
                logging.info(
                    "A new risitas has been inserted in the database!"
                )
                logging.debug(
                    f"Id: {cursor.lastrowid} "
                    f"Title: {title} "
                    f"Current page: {current_page} "
                    f"Total pages : {total_pages}"
                )
                for author in authors:
                    con.execute(
                        '''INSERT INTO authors
                        (name, risitas_id)
                        VALUES (?, ?)''',
                        (
                            author,
                            cursor.lastrowid,
                        )
                    )
                    logging.debug(
                        f"Author : {author} "
                        "has been inserted in the database!"
                    )
        except sqlite3.OperationalError as e:
            logging.exception(e)
    con.close()


def delete_db() -> None:
    DB_PATH.unlink()
    logging.info(f"Deleted database at {DB_PATH}")
