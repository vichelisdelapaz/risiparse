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
    con = sqlite3.connect(DB_PATH)
    try:
        with con:
            cursor = con.execute(
                '''select * from risitas where page_link = ?''',
                (page_link, )
            )
            risitas_row = cursor.fetchone()
            cursor_author = con.execute(
                '''select name from authors where risitas_id = ?''',
                (risitas_row[0], )
            )
            authors_row = cursor_author.fetchall()
    except sqlite3.IntegrityError as e:
        logging.exception(e)
    con.close()
    return risitas_row, authors_row


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
    file_path_str = str(file_path)
    con = sqlite3.connect(DB_PATH)
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

