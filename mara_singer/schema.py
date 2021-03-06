from functools import singledispatch

from mara_db import dbs


@singledispatch
def jsonschema_to_sql_create_table(db: object, jsonschema, table_name: str = None, key_properties: [str] = None, properties: [str] = None, create_if_not_exists: bool = False) -> str:
    """
    Creates an SQL create table statement from an JSON schema.

    Args:
        db: The destination db object
        jsonschema: The JSON schema.
        table_name: The destination table name.
        key_properties: (Optional) The properties which are key properties, so, they must be provided (NOT NULL)
        properties: (Optional) The properties which shall be added to the table. If not given, all properties will be added to the table. Note: properties from key_properties are always added.
        create_if_not_exists: If the SQL create table statement should be a 'CREATE TABLE IF NOT EXISTS' statement.
    """
    raise NotImplementedError(f'Please implement jsonschema_to_sql_create_table for type "{db.__class__.__name__}"')

@jsonschema_to_sql_create_table.register(str)
def __(alias: str, jsonschema, table_name: str = None, key_properties: [str] = None, properties: [str] = None, create_if_not_exists: bool = False) -> str:
    return jsonschema_to_sql_create_table(dbs.db(alias), jsonschema=jsonschema, table_name=table_name, key_properties=key_properties, properties=properties, create_if_not_exists=create_if_not_exists)

@jsonschema_to_sql_create_table.register(dbs.PostgreSQLDB)
def __(db: dbs.PostgreSQLDB, jsonschema, table_name: str = None, key_properties: [str] = None, properties: [str] = None, create_if_not_exists: bool = False):
    if jsonschema.get('type') != 'object' and jsonschema.get('type') != ['null', 'object']:
        raise Exception('The JSON schema must be of type object to be convertable to a SQL table')
    if 'additionalProperties' in jsonschema and jsonschema['additionalProperties'] == True:
        raise Exception('The JSON schema must not allow additional properties in its main object to be convertable to a SQL table')

    fields = []
    for property_name, property_definition in jsonschema['properties'].items():
        if not properties or (property_name in properties or (key_properties and property_name in key_properties)):
            fields.append(_jsonschema_property_to_sql_field_definition(db, property_name, property_definition, key_properties))

    if create_if_not_exists:
        sql = 'CREATE TABLE IF NOT EXISTS {} (\n  {}\n)'.format(table_name, ',\n  '.join(fields))
    else:
        sql = 'CREATE TABLE {} (\n  {}\n)'.format(table_name, ',\n  '.join(fields))

    return sql

@jsonschema_to_sql_create_table.register(dbs.BigQueryDB)
def __(db: dbs.BigQueryDB, jsonschema, table_name: str = None, key_properties: [str] = None, properties: [str] = None, create_if_not_exists: bool = False):
    if jsonschema.get('type') != 'object' and jsonschema.get('type') != ['null', 'object']:
        raise Exception('The JSON schema must be of type object to be convertable to a SQL table')
    if 'additionalProperties' in jsonschema and jsonschema['additionalProperties'] == True:
        raise Exception('The JSON schema must not allow additional properties in its main object to be convertable to a SQL table')

    fields = []
    for property_name, property_definition in jsonschema['properties'].items():
        if not properties or (property_name in properties or (key_properties and property_name in key_properties)):
            fields.append(_jsonschema_property_to_sql_field_definition(db, property_name, property_definition, key_properties))

    if create_if_not_exists:
        sql = 'CREATE TABLE IF NOT EXISTS {} (\n  {}\n)'.format(table_name, ',\n  '.join(fields))
    else:
        sql = 'CREATE TABLE {} (\n  {}\n)'.format(table_name, ',\n  '.join(fields))

    return sql


@singledispatch
def _jsonschema_property_type_to_db_type(db: object, type: str, format: str = None):
    raise NotImplementedError(f'Please implement _jsonschema_property_type_map for type "{db.__class__.__name__}"')

@_jsonschema_property_type_to_db_type.register(dbs.PostgreSQLDB)
def __(db: dbs.PostgreSQLDB, type, format = None):
    if type == 'string':
        if format == 'date':
            return 'DATE'
        if format == 'date-time':
            return 'TIMESTAMP'
        return 'TEXT'
    if type == 'boolean':
        return 'BOOLEAN'
    if type == 'integer':
        return 'BIGINT'

    raise Exception(f'Could not map type \'{type}\' with format \'{format}\'')

@_jsonschema_property_type_to_db_type.register(dbs.BigQueryDB)
def __(db: dbs.BigQueryDB, type, format = None):
    if type == 'string':
        if format == 'date':
            return 'DATE'
        if format == 'date-time':
            return 'TIMESTAMP'
        return 'STRING'
    if type == 'boolean':
        return 'BOOL'
    if type == 'integer':
        return 'INT64'
    if type == 'number':
        return 'NUMERIC'

    raise Exception(f'Could not map type \'{type}\' with format \'{format}\'')


@singledispatch
def _jsonschema_property_to_sql_field_definition(db: object, property_name, property_definition, key_properties: [str] = None, ignore_nullable: bool = False):
    raise NotImplementedError(f'Please implement _jsonschema_property_to_sql_field_definition for type "{db.__class__.__name__}"')

@_jsonschema_property_to_sql_field_definition.register(dbs.PostgreSQLDB)
def __(db: dbs.PostgreSQLDB, property_name, property_definition, key_properties: [str] = None, ignore_nullable: bool = False):
    field_type = None
    is_nullable = None

    if not field_type and 'type' in property_definition:
        if isinstance(property_definition['type'], list):
            typeList = property_definition['type']
        else:
            typeList = [property_definition['type']]

        for type in typeList:
            if type == "null":
                is_nullable = True
            elif type == "object":
                raise NotImplementedError('JSON object type --> Composite type creation is not yet implemented for PostgreSQLDB')
            elif type == "array":
                if 'items' in property_definition:
                    field_type = '{}[]'.format(_jsonschema_property_to_sql_field_definition(db, property_name=None, property_definition=property_definition['items']))
            else:
                # hack for tap-adwords:
                if field_type:
                    continue # sometimes e.g. tap-adwords has 'null, integer, string' as a type --> is the money type. We assume here always to use the integer value

                if 'format' in property_definition:
                    field_type = _jsonschema_property_type_to_db_type(db, type=type, format=property_definition['format'])
                else:
                    field_type = _jsonschema_property_type_to_db_type(db, type=type)

    if not field_type and 'anyOf' in property_definition:
        if property_definition['anyOf'][0]['type'] != "array":
            raise "Unexpected type for property {}".format(property_name)

        field_type = '{}[]'.format(property_definition['anyOf'][0]['items']['type'])

        if property_definition['anyOf'][1]['type'] == "null":
            is_nullable = True

    if not field_type:
        raise Exception(f'Could not determine field type for property {property_name}')

    if is_nullable and key_properties and property_name in key_properties:
        is_nullable = False

    if is_nullable and not ignore_nullable:
        if not property_name:
            return field_type
        return '{} {}'.format(property_name, field_type)
    else:
        if not property_name:
            return field_type
        return '{} {} NOT NULL'.format(property_name, field_type)

@_jsonschema_property_to_sql_field_definition.register(dbs.BigQueryDB)
def __(db: dbs.BigQueryDB, property_name, property_definition, key_properties: [str] = None, ignore_nullable: bool = False):
    field_type = None
    is_nullable = None

    if not field_type and 'type' in property_definition:
        if isinstance(property_definition['type'], list):
            typeList = property_definition['type']
        else:
            typeList = [property_definition['type']]

        for type in typeList:
            if type == "null":
                is_nullable = True
            elif type == "object":
                if 'properties' in property_definition:
                    sub_properties = []
                    for sub_property_name, sub_property_definition in property_definition['properties'].items():
                        sub_properties.append(_jsonschema_property_to_sql_field_definition(db, property_name=sub_property_name, property_definition=sub_property_definition))

                    if len(sub_properties) == 0:
                        field_type = 'STRING'
                    else:
                        field_type = 'STRUCT<{}>'.format(', '.join(sub_properties))
                else:
                    raise Exception(f'Unknown usage of type {type} for property {property_name}')
            elif type == "array":
                if 'items' in property_definition:
                    field_type = 'ARRAY<{}>'.format(_jsonschema_property_to_sql_field_definition(db, property_name=None, property_definition=property_definition['items']))
            else:
                # hack for tap-adwords:
                if field_type:
                    continue # sometimes e.g. tap-adwords has 'null, integer, string' as a type --> is the money type. We assume here always to use the integer value

                if 'format' in property_definition:
                    field_type = _jsonschema_property_type_to_db_type(db, type=type, format=property_definition['format'])
                else:
                    field_type = _jsonschema_property_type_to_db_type(db, type=type)

    if not field_type and 'anyOf' in property_definition:
        if property_definition['anyOf'][0]['type'] != "array":
            raise "Unexpected type for property {}".format(property_name)

        field_type = 'ARRAY<{}>'.format(property_definition['anyOf'][0]['items']['type'])

        if property_definition['anyOf'][1]['type'] == "null":
            is_nullable = True

    if not field_type:
        raise Exception(f'Could not determine field type for property {property_name}')

    if is_nullable and key_properties and property_name in key_properties:
        is_nullable = False

    # Big Query does not support NOT NULL arrays. When you try to create a column with ARRAY<> NOT NULL, you get the error:
    #   NOT NULL cannot be applied to ARRAY field '<COLUMN_NAME>'. NULL arrays are always stored as an empty array.
    if str.startswith(field_type, 'ARRAY') and not is_nullable:
        is_nullable = True

    if is_nullable and not ignore_nullable:
        if not property_name:
            return field_type
        return '{} {}'.format(property_name, field_type)
    else:
        if not property_name:
            return field_type
        return '{} {} NOT NULL'.format(property_name, field_type)
