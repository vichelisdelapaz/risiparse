#!/usr/bin/python3

from typing import List
import sqlite3
import pathlib
import logging

DB_PATH = pathlib.Path(__file__).parent.parent.parent / "risiparse.db"

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
    except sqlite3.IntegrityError as e:
        logging.exception(e)
    con.close()


def read_db(page_link: str):
    create_db()
    con = sqlite3.connect(DB_PATH)
    try:
        with con:
            cursor = con.execute(
                '''select * from risitas where page_link = ?''',
                (page_link, )
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
    except sqlite3.IntegrityError as e:
        logging.exception(e)
    con.close()
    return rows


def update_db(
        domain: str,
        title: str,
        page_link: str,
        file_path: str,
        total_pages: int,
        current_page: int,
        message_cursor: int,
        authors: List,
) -> None:
    create_db()
    # Need to handle the updates of existing rows
    file_path_str = str(file_path)
    con = sqlite3.connect(DB_PATH)
    cursor_existing_row = con.execute(
        '''select id from risitas where page_link = ? limit 1''', (page_link, )
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
                cursor_existing_row = con.execute(
                    '''select name from authors where id = ?''', (cursor_existing_row[0], )
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
        except sqlite3.IntegrityError as e:
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
        except sqlite3.IntegrityError as e:
            logging.exception(e)
    con.close()


def delete_db() -> None:
    DB_PATH.unlink()
    logging.info(f"Deleted database at {DB_PATH}")

