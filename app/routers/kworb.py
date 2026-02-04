from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Generator, List
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

router = APIRouter(prefix="/kworb", tags=["kworb"])

#create engine once at module level for connection pooling
_kworb_engine = None


def get_kworb_engine():
    global _kworb_engine
    if _kworb_engine is None:
        if not settings.KWORB_DATABASE_URL:
            raise HTTPException(status_code=503, detail="Kworb database not configured")
        _kworb_engine = create_engine(str(settings.KWORB_DATABASE_URL))
    return _kworb_engine


def get_kworb_db() -> Generator[Session, None, None]:
    """Get a connection to the Kworb scraper database"""
    engine = get_kworb_engine()
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class TopStreamedArtist(BaseModel):
    rank: int
    artist: str
    streams: float
    daily: float
    as_lead: float
    solo: float
    as_feature: float


class MonthlyListeners(BaseModel):
    rank: int
    artist: str
    listeners: int
    peak: int
    peak_listeners: int


class TopSongStreams(BaseModel):
    rank: int
    artist_and_title: str
    streams: int
    daily: float


@router.get("/top-streamed-artists", response_model=List[TopStreamedArtist])
def get_top_streamed_artists(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_kworb_db),
):
    """Get top streamed artists"""
    result = db.execute(
        text("""
            SELECT "Rank", "Artist", "Streams", "Daily", "As lead", "Solo", "As feature"
            FROM spotify_top_streamed_artists
            ORDER BY "Rank" ASC
            LIMIT :limit OFFSET :offset
        """),
        {"limit": limit, "offset": offset},
    )
    rows = result.fetchall()
    return [TopStreamedArtist(rank=row[0], artist=row[1], streams=row[2], daily=row[3], as_lead=row[4], solo=row[5], as_feature=row[6]) for row in rows]


@router.get("/monthly-listeners", response_model=List[MonthlyListeners])
def get_monthly_listeners(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_kworb_db),
):
    """Get artist monthly listeners"""
    result = db.execute(
        text("""
            SELECT "Rank", "Artist", "Listeners", "Peak", "PkListeners"
            FROM spotify_artist_monthly_listeners
            ORDER BY "Rank" ASC
            LIMIT :limit OFFSET :offset
        """),
        {"limit": limit, "offset": offset},
    )
    rows = result.fetchall()
    return [MonthlyListeners(rank=row[0], artist=row[1], listeners=row[2], peak=row[3], peak_listeners=row[4]) for row in rows]


@router.get("/top-songs", response_model=List[TopSongStreams])
def get_top_songs(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_kworb_db),
):
    """Get top song streams"""
    result = db.execute(
        text("""
            SELECT "Rank", "Artist and Title", "Streams", "Daily"
            FROM spotify_top_song_streams
            ORDER BY "Rank" ASC
            LIMIT :limit OFFSET :offset
        """),
        {"limit": limit, "offset": offset},
    )
    rows = result.fetchall()
    return [TopSongStreams(rank=row[0], artist_and_title=row[1], streams=row[2], daily=row[3]) for row in rows]


@router.get("/artist/{artist_name}")
def search_artist(artist_name: str, db: Session = Depends(get_kworb_db)):
    """Search for an artist across all data"""
    #search in top streamed artists
    streamed = db.execute(
        text("""
            SELECT "Rank", "Artist", "Streams", "Daily", "As lead", "Solo", "As feature"
            FROM spotify_top_streamed_artists
            WHERE LOWER("Artist") LIKE LOWER(:name)
            LIMIT 10
        """),
        {"name": f"%{artist_name}%"},
    ).fetchall()

    #search in monthly listeners
    listeners = db.execute(
        text("""
            SELECT "Rank", "Artist", "Listeners", "Peak", "PkListeners"
            FROM spotify_artist_monthly_listeners
            WHERE LOWER("Artist") LIKE LOWER(:name)
            LIMIT 10
        """),
        {"name": f"%{artist_name}%"},
    ).fetchall()

    #search in top songs
    songs = db.execute(
        text("""
            SELECT "Rank", "Artist and Title", "Streams", "Daily"
            FROM spotify_top_song_streams
            WHERE LOWER("Artist and Title") LIKE LOWER(:name)
            LIMIT 10
        """),
        {"name": f"%{artist_name}%"},
    ).fetchall()

    return {
        "top_streamed": [TopStreamedArtist(rank=row[0], artist=row[1], streams=row[2], daily=row[3], as_lead=row[4], solo=row[5], as_feature=row[6]) for row in streamed],
        "monthly_listeners": [MonthlyListeners(rank=row[0], artist=row[1], listeners=row[2], peak=row[3], peak_listeners=row[4]) for row in listeners],
        "top_songs": [TopSongStreams(rank=row[0], artist_and_title=row[1], streams=row[2], daily=row[3]) for row in songs],
    }
