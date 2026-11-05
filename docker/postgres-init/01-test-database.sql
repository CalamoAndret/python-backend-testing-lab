-- Development only. Tests never run against the application database.
SELECT 'CREATE DATABASE testing_lab_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'testing_lab_test')
\gexec
