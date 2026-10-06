"""Application use cases shared by transport adapters.

Domain rules stay in career/league/engine. These services coordinate use cases;
they do not create HTTP servers, start UI windows, or select a save directory.
Legacy tools imports are compatibility aliases during the migration.
"""
