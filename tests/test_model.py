import pytest

from src.model import Playlist

class TestPlaylist:

    @pytest.mark.parametrize(
        "start,end,current,expected,priority",
        [
            # --- Non-wrapping cases 09:00 <-> 15:00 ---
            ("09:00", "15:00", "08:59", False, 360),  # just before start
            ("09:00", "15:00", "09:00", True, 360),   # exactly at start
            ("09:00", "15:00", "12:00", True, 360),   # during
            ("09:00", "15:00", "14:59", True, 360),   # just before end
            ("09:00", "15:00", "15:00", False, 360),  # exactly at end
            ("09:00", "15:00", "23:00", False, 360),  # way after
    
            # --- Wrapping cases (crossing midnight) 21:00 <-> 03:00 ---
            ("21:00", "03:00", "20:59", False, 360),  # just before start
            ("21:00", "03:00", "21:00", True, 360),   # exactly at start
            ("21:00", "03:00", "23:59", True, 360),   # before midnight
            ("21:00", "03:00", "00:00", True, 360),   # after midnight, inside
            ("21:00", "03:00", "02:59", True, 360),   # just before end
            ("21:00", "03:00", "03:00", False, 360),  # exactly at end
            ("21:00", "03:00", "11:00", False, 360),  # way after
    
            # --- Equal start and end 12:00 <-> 12:00 ---
            ("12:00", "12:00", "11:59", False, 0),
            ("12:00", "12:00", "12:00", False, 0),
            ("12:00", "12:00", "12:01", False, 0),
    
            # --- Midnight boundaries 18:00 <-> 00:00 ---
            ("18:00", "00:00", "17:59", False, 360),  # before start
            ("18:00", "00:00", "23:59", True, 360),   # before end
            ("18:00", "00:00", "00:00", False, 360),  # exactly at end
    
            # --- Midnight boundaries 00:00 <-> 06:00 ---
            ("00:00", "06:00", "00:00", True, 360),   # start at midnight
            ("00:00", "06:00", "05:59", True, 360),   # before end
            ("00:00", "06:00", "06:00", False, 360),  # exactly at end

            # --- All day 00:00 <-> 24:00 ---
            ("00:00", "24:00", "00:00", True, 1440),   # exactly at start
            ("00:00", "24:00", "10:00", True, 1440),   # during
            ("00:00", "24:00", "24:00", False, 1440),  # exactly at end
        ]
    )
    def test_is_active_and_priority(self, start, end, current, expected, priority):
        playlist = Playlist("Test Playlist", start, end)
        assert playlist.is_active(current) == expected
        assert playlist.get_priority() == priority
        

class TestPlaylistRotation:

    def make_manager(self):
        from datetime import datetime
        from src.model import PlaylistManager, PluginInstance
        def playlist(name, start, end, plugins):
            p = Playlist(name, start, end)
            p.plugins = [PluginInstance("clock", f"{name}-{i}", {}, {}) for i in range(plugins)]
            return p
        manager = PlaylistManager([
            playlist("Allday", "00:00", "24:00", 2),
            playlist("Morning", "08:00", "12:00", 1),
            playlist("Empty", "09:00", "10:00", 0),
        ])
        return manager, datetime(2026, 10, 25, 9, 30)

    def test_rotates_between_playlists_active_at_the_same_time(self):
        manager, now = self.make_manager()
        shown = []
        for _ in range(4):
            playlist = manager.determine_next_playlist(now)
            manager.active_playlist = playlist.name
            shown.append(playlist.name)
        # shortest range first, then take turns; playlists without plugins are skipped
        assert shown == ["Morning", "Allday", "Morning", "Allday"]

    def test_active_playlist_stays_while_it_is_active(self):
        manager, now = self.make_manager()
        manager.active_playlist = "Allday"
        assert manager.determine_active_playlist(now).name == "Allday"
        manager.active_playlist = "Gone"
        assert manager.determine_active_playlist(now).name == "Empty"

    def test_single_active_playlist(self):
        from datetime import datetime
        manager, _ = self.make_manager()
        evening = datetime(2026, 10, 25, 20, 0)
        manager.active_playlist = "Allday"
        assert manager.determine_next_playlist(evening).name == "Allday"
