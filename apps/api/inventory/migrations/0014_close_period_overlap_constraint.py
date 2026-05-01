from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0013_masteritem_parent_company"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            CREATE OR REPLACE FUNCTION inventory_close_period_prevent_overlap()
            RETURNS trigger AS $$
            BEGIN
                PERFORM pg_advisory_xact_lock(hashtextextended(NEW.organization_id::text, 0));

                IF EXISTS (
                    SELECT 1
                    FROM inventory_inventorycloseperiod existing
                    WHERE existing.organization_id = NEW.organization_id
                      AND existing.id <> COALESCE(NEW.id, -1)
                      AND existing.start_date <= NEW.end_date
                      AND existing.end_date >= NEW.start_date
                ) THEN
                    RAISE EXCEPTION 'Inventory close period overlaps an existing period for this organisation.'
                        USING ERRCODE = '23P01';
                END IF;

                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            CREATE TRIGGER inventory_close_period_no_overlap
            BEFORE INSERT OR UPDATE OF organization_id, start_date, end_date
            ON inventory_inventorycloseperiod
            FOR EACH ROW
            EXECUTE FUNCTION inventory_close_period_prevent_overlap();
            """,
            reverse_sql="""
            DROP TRIGGER IF EXISTS inventory_close_period_no_overlap
            ON inventory_inventorycloseperiod;
            DROP FUNCTION IF EXISTS inventory_close_period_prevent_overlap();
            """,
        ),
    ]
