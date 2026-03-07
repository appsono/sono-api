"""tests for collection endpoints"""

from app.core.config import settings


def test_create_collection(client, auth_headers):
    """test creating a new collection"""
    response = client.post(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
        json={
            "title": "My Test Collection",
            "description": "A test collection",
            "collection_type": "playlist",
            "is_public": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "My Test Collection"
    assert data["description"] == "A test collection"
    assert data["collection_type"] == "playlist"
    assert "id" in data


def test_create_collection_unauthorized(client):
    """test creating collection without auth fails"""
    response = client.post(
        f"{settings.API_V1_STR}/collections/",
        json={
            "title": "Test Collection",
            "collection_type": "playlist",
        },
    )
    assert response.status_code == 401


def test_get_user_collections(client, auth_headers):
    """test getting users collections"""
    client.post(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
        json={
            "title": "Test Collection",
            "collection_type": "playlist",
        },
    )

    response = client.get(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "collections" in data
    assert "total" in data
    assert "has_more" in data
    assert isinstance(data["collections"], list)
    assert data["total"] >= 1


def test_get_collection_by_id(client, auth_headers):
    """test getting a specific collection"""
    create_response = client.post(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
        json={
            "title": "Test Collection",
            "collection_type": "album",
        },
    )
    collection_id = create_response.json()["id"]

    response = client.get(
        f"{settings.API_V1_STR}/collections/{collection_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == collection_id
    assert data["title"] == "Test Collection"


def test_update_collection(client, auth_headers):
    """Test updating a collection"""
    create_response = client.post(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
        json={
            "title": "Original Title",
            "collection_type": "playlist",
        },
    )
    collection_id = create_response.json()["id"]

    response = client.put(
        f"{settings.API_V1_STR}/collections/{collection_id}",
        headers=auth_headers,
        json={
            "title": "Updated Title",
            "description": "Updated description",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["description"] == "Updated description"


def test_delete_collection(client, auth_headers):
    """test deleting a collection"""
    create_response = client.post(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
        json={
            "title": "To Be Deleted",
            "collection_type": "playlist",
        },
    )
    collection_id = create_response.json()["id"]

    response = client.delete(
        f"{settings.API_V1_STR}/collections/{collection_id}",
        headers=auth_headers,
    )
    assert response.status_code == 200

    get_response = client.get(
        f"{settings.API_V1_STR}/collections/{collection_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404


def test_get_public_collections(client):
    """test getting public collections without auth"""
    response = client.get(f"{settings.API_V1_STR}/collections/?public_only=true")
    assert response.status_code == 200
    data = response.json()
    assert "collections" in data
    assert "total" in data
    assert isinstance(data["collections"], list)


def test_get_collection_stats(client, auth_headers):
    """test getting collection statistics"""
    response = client.get(
        f"{settings.API_V1_STR}/collections/stats",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "total_collections" in data
    assert isinstance(data["total_collections"], int)


def test_update_other_user_collection_fails(client, auth_headers, test_superuser, db_session):
    """test that users cannot update other users' collections"""
    from app import models

    collection = models.Collection(
        title="Admin Collection",
        collection_type="playlist",
        owner_id=test_superuser.id,
        is_public=False,
    )
    db_session.add(collection)
    db_session.commit()
    db_session.refresh(collection)

    response = client.put(
        f"{settings.API_V1_STR}/collections/{collection.id}",
        headers=auth_headers,
        json={"title": "Hacked Title"},
    )
    assert response.status_code in [403, 404]


def test_create_album_with_artist(client, auth_headers):
    """test creating an album with artist field"""
    response = client.post(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
        json={
            "title": "Test Album",
            "collection_type": "album",
            "artist": "Test Artist",
            "is_public": True,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["collection_type"] == "album"
    assert data["artist"] == "Test Artist"


def test_create_compilation_with_note(client, auth_headers):
    """test creating a compilation with curator note"""
    response = client.post(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
        json={
            "title": "Test Compilation",
            "collection_type": "compilation",
            "curator_note": "Curated with care",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["collection_type"] == "compilation"
    assert data["curator_note"] == "Curated with care"


def test_delete_other_user_collection_fails(client, auth_headers, test_superuser, db_session):
    """non-owners cannot delete collections"""
    from app import models

    collection = models.Collection(
        title="Not Yours",
        collection_type="playlist",
        owner_id=test_superuser.id,
        is_public=False,
    )
    db_session.add(collection)
    db_session.commit()
    db_session.refresh(collection)

    response = client.delete(
        f"{settings.API_V1_STR}/collections/{collection.id}",
        headers=auth_headers,
    )
    assert response.status_code in [403, 404]


def test_get_nonexistent_collection(client, auth_headers):
    """test 404 for nonexistent collection"""
    response = client.get(
        f"{settings.API_V1_STR}/collections/99999",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_private_collection_hidden_from_public(client, auth_headers, db_session):
    """private collections should not appear in public listings"""
    client.post(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
        json={
            "title": "Private Playlist",
            "collection_type": "playlist",
            "is_public": False,
        },
    )

    response = client.get(f"{settings.API_V1_STR}/collections/?public_only=true")
    assert response.status_code == 200
    data = response.json()
    titles = [c["title"] for c in data["collections"]]
    assert "Private Playlist" not in titles


def test_my_collections_only_returns_own(client, auth_headers, test_superuser, db_session):
    """my-collections should only return the current user's collections"""
    from app import models

    # create collection owned by another user
    other_collection = models.Collection(
        title="Not Mine",
        collection_type="playlist",
        owner_id=test_superuser.id,
        is_public=True,
    )
    db_session.add(other_collection)
    db_session.commit()

    # create own collection
    client.post(
        f"{settings.API_V1_STR}/collections/",
        headers=auth_headers,
        json={
            "title": "Mine",
            "collection_type": "playlist",
        },
    )

    response = client.get(
        f"{settings.API_V1_STR}/collections/my-collections",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    titles = [c["title"] for c in data["collections"]]
    assert "Mine" in titles
    assert "Not Mine" not in titles
