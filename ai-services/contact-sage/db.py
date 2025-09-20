# contact-sage/db.py
"""
Database Management Module

This module provides a high-level abstraction for interacting with the `contacts`
table in the PostgreSQL database using SQLAlchemy Core.
"""

import logging
from sqlalchemy import create_engine, MetaData, Table, Column, String, Boolean, and_
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor


class ContactsDb:
    """
    ContactsDb provides a set of helper functions over SQLAlchemy
    to handle database operations for the contact service.
    """

    def __init__(self, uri, logger=logging):
        """
        Initializes the database engine and table metadata.
        """
        self.engine = create_engine(uri)
        self.logger = logger
        self.metadata = MetaData()
        self.contacts_table = Table(
            "contacts",
            self.metadata,
            Column("username", String, nullable=False),
            Column("label", String, nullable=False),
            Column("account_num", String, nullable=False),
            Column("routing_num", String, nullable=False),
            Column("is_external", Boolean, nullable=False),
        )
        # ADDED: Definition for the 'users' table to allow for validation queries.
        self.users_table = Table(
            "users",
            self.metadata,
            Column("accountid", String, primary_key=True),
            Column("username", String, nullable=False),
        )

        SQLAlchemyInstrumentor().instrument(
            engine=self.engine,
            service="contacts", # This service name is for tracing.
        )
    
    # ADDED: New function to check if a user exists by their account number.
    def check_user_exists(self, account_num):
        """
        Checks if a user exists in the 'users' table with the given account number.

        Params: account_num - the account number (accountid) to check.
        Return: True if the user exists, False otherwise.
        """
        with self.engine.connect() as conn:
            query = self.users_table.select().where(self.users_table.c.accountid == account_num)
            result = conn.execute(query).first()
        return result is not None

    def add_contact(self, contact: dict):
        """Inserts a new contact into the database."""
        with self.engine.connect() as conn:
            insert_stmt = self.contacts_table.insert().values(
                username=contact["username"],
                label=contact["label"],
                account_num=contact["account_num"],
                routing_num=contact["routing_num"],
                is_external=contact["is_external"],
            )
            conn.execute(insert_stmt)
            conn.commit()

    def get_contacts(self, username: str) -> list:
        """Retrieves all contacts for a specified username."""
        with self.engine.connect() as conn:
            select_stmt = self.contacts_table.select().where(
                self.contacts_table.c.username == username
            )
            result = conn.execute(select_stmt)
            contacts = [dict(row) for row in result.mappings()]
            return contacts

    def update_contact(self, username: str, old_label: str, new_contact_data: dict) -> int:
        """Atomically updates an existing contact. Returns the number of rows updated."""
        with self.engine.connect() as conn:
            update_stmt = self.contacts_table.update().where(
                and_(
                    self.contacts_table.c.username == username,
                    self.contacts_table.c.label == old_label
                )
            ).values(new_contact_data)
            result = conn.execute(update_stmt)
            conn.commit()
            return result.rowcount

    def delete_contact(self, username: str, label: str) -> int:
        """Deletes a contact. Returns the number of rows deleted."""
        with self.engine.connect() as conn:
            delete_stmt = self.contacts_table.delete().where(
                and_(
                    self.contacts_table.c.username == username,
                    self.contacts_table.c.label == label
                )
            )
            result = conn.execute(delete_stmt)
            conn.commit()
            return result.rowcount