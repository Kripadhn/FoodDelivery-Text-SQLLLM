SELECT 'order_id' AS column_name, COUNT(DISTINCT order_id) AS cnt, ARRAY_AGG(DISTINCT order_id) AS values FROM `hive_metastore`.online_food_business.orders 
UNION ALL 
SELECT 'user_id' AS column_name, COUNT(DISTINCT user_id) AS cnt, ARRAY_AGG(DISTINCT user_id) AS values FROM `hive_metastore`.online_food_business.orders 
UNION ALL 
SELECT 'delivery_address' AS column_name, COUNT(DISTINCT delivery_address) AS cnt, ARRAY_AGG(DISTINCT delivery_address) AS values FROM `hive_metastore`.online_food_business.orders 
UNION ALL 
SELECT 'order_status' AS column_name, COUNT(DISTINCT order_status) AS cnt, ARRAY_AGG(DISTINCT order_status) AS values FROM `hive_metastore`.online_food_business.orders 
UNION ALL 
SELECT 'restaurant_id' AS column_name, COUNT(DISTINCT restaurant_id) AS cnt, ARRAY_AGG(DISTINCT restaurant_id) AS values FROM `hive_metastore`.online_food_business.orders