CREATE TRIGGER IF NOT EXISTS stock_alert_on_create
AFTER INSERT ON components
WHEN NEW.deleted_at IS NULL AND (NEW.quantity = 0 OR NEW.quantity <= NEW.reorder_level)
BEGIN
    INSERT INTO stock_alerts (component_id, status, quantity, reorder_level)
    VALUES (NEW.id, CASE WHEN NEW.quantity = 0 THEN 'Out of Stock' ELSE 'Low Stock' END,
            NEW.quantity, NEW.reorder_level);
END;

CREATE TRIGGER IF NOT EXISTS stock_alert_on_transition
AFTER UPDATE OF quantity, reorder_level ON components
WHEN NEW.deleted_at IS NULL
 AND (NEW.quantity = 0 OR NEW.quantity <= NEW.reorder_level)
 AND (CASE WHEN OLD.quantity = 0 THEN 0 WHEN OLD.quantity <= OLD.reorder_level THEN 1 ELSE 2 END)
     != (CASE WHEN NEW.quantity = 0 THEN 0 WHEN NEW.quantity <= NEW.reorder_level THEN 1 ELSE 2 END)
BEGIN
    INSERT INTO stock_alerts (component_id, status, quantity, reorder_level)
    VALUES (NEW.id, CASE WHEN NEW.quantity = 0 THEN 'Out of Stock' ELSE 'Low Stock' END,
            NEW.quantity, NEW.reorder_level);
END;
