from app import create_app, db


def test_admin_routes_require_login(tmp_path):
    app = create_app({'TESTING': True, 'SECRET_KEY': 'test-secret',
                      'SQLALCHEMY_DATABASE_URI': 'sqlite://', 'WTF_CSRF_ENABLED': False,
                      'SESSION_FILE_DIR': str(tmp_path / 'sessions')})
    client = app.test_client()
    response = client.get('/admin')
    assert response.status_code == 302
    assert '/admin/login' in response.headers['Location']
    with app.app_context():
        db.drop_all()
