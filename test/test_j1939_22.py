"""
Tests for J1939-22 transport protocol chunking logic.

This module tests the data chunking algorithm used in J1939-22 for splitting
large messages into transport protocol segments of 60 bytes each.
"""
import pytest

from j1939.j1939_22 import J1939_22
from j1939.message_id import FrameFormat
from test_helpers.conftest import feeder


class TestChunkingAlgorithm:
    """Isolated tests for the data chunking algorithm."""
    
    @staticmethod
    def chunk_data(data, chunk_size):
        """Pure-Python chunking implementation matching j1939_22.py:send_pgn()"""
        data_length = len(data)
        return [list(data[i:i + chunk_size]) for i in range(0, data_length, chunk_size)]
    
    @pytest.mark.parametrize("data_length,expected_chunks,expected_last_chunk_size", [
        (60, 1, 60),
        (61, 2, 1),
        (119, 2, 59),
        (120, 2, 60),
        (121, 3, 1),
        (180, 3, 60),
        (181, 4, 1),
    ])
    def test_chunk_sizes(self, data_length, expected_chunks, expected_last_chunk_size):
        """Verify correct chunk count and sizes for various data lengths."""
        data = list(range(data_length))
        result = self.chunk_data(data, J1939_22.DataLength.TP)
        
        assert len(result) == expected_chunks
        assert len(result[-1]) == expected_last_chunk_size
    
    def test_data_integrity(self):
        """All original bytes are present after chunking, in correct order."""
        data = list(range(2560))  # Large data set: 43 chunks
        result = self.chunk_data(data, J1939_22.DataLength.TP)
        
        # Verify chunk count
        expected_chunks = 2560 // J1939_22.DataLength.TP + (1 if 2560 % J1939_22.DataLength.TP else 0)
        assert len(result) == expected_chunks
        
        # Verify all data preserved in order
        reconstructed = []
        for chunk in result:
            reconstructed.extend(chunk)
        assert reconstructed == data
    
    def test_chunk_count_matches_num_segments_formula(self):
        """Verify chunking matches the num_segments formula used in j1939_22.py."""
        for data_length in [60, 61, 119, 120, 121, 180, 500, 1000]:
            data = [i % 256 for i in range(data_length)]
            
            result = self.chunk_data(data, J1939_22.DataLength.TP)
            
            # Formula from j1939_22.py
            expected = int(data_length / J1939_22.DataLength.TP) + ((data_length % J1939_22.DataLength.TP) != 0)
            
            assert len(result) == expected, f"data_length={data_length}"


class TestJ1939_22Integration:
    """Integration tests for J1939-22 chunking through send_pgn."""
    
    @staticmethod
    def create_j1939_22():
        """Create a J1939_22 instance with mock callbacks."""
        return J1939_22(
            send_message=lambda *args, **kwargs: None,
            job_thread_wakeup=lambda: None,
            notify_subscribers=lambda *args: None,
            max_cmdt_packets=16,
            minimum_tp_rts_cts_dt_interval=None,
            minimum_tp_bam_dt_interval=0.010,
            ecu_is_message_acceptable=lambda dest: True
        )
    
    def test_short_message_not_chunked(self, feeder):
        """Data <= J1939_22.DataLength.TP bytes uses multi-pg path, not TP chunking."""
        feeder.accept_all_messages()
        j1939_22 = self.create_j1939_22()
        
        result = j1939_22.send_pgn(
            data_page=0, pdu_format=0xFE, pdu_specific=0xFF,
            priority=7, src_address=0x01, data=list(range(J1939_22.DataLength.TP)),
            time_limit=0, frame_format=FrameFormat.CEFF
        )
        
        assert result is True
        assert len(j1939_22._snd_buffer) == 0
    
    def test_bam_broadcast_chunking(self, feeder):
        """BAM broadcast correctly chunks data and verifies integrity."""
        feeder.accept_all_messages()
        j1939_22 = self.create_j1939_22()
        
        test_data = list(range(121))  # 3 chunks: 60 + 60 + 1
        
        result = j1939_22.send_pgn(
            data_page=0, pdu_format=0xFE, pdu_specific=0xFF,
            priority=7, src_address=0x01, data=test_data,
            time_limit=0, frame_format=FrameFormat.CEFF
        )
        
        assert result is True
        buffer = list(j1939_22._snd_buffer.values())[0]
        
        assert buffer['num_segments'] == 3
        assert len(buffer['data']) == 3
        assert [len(chunk) for chunk in buffer['data']] == [60, 60, 1]
        
        # Verify data integrity
        reconstructed = []
        for chunk in buffer['data']:
            reconstructed.extend(chunk)
        assert reconstructed == test_data
    
    def test_rts_cts_peer_to_peer_chunking(self, feeder):
        """RTS/CTS peer-to-peer uses different code path but chunks correctly."""
        feeder.accept_all_messages()
        j1939_22 = self.create_j1939_22()
        
        test_data = list(range(180))  # 3 chunks of 60 each
        
        result = j1939_22.send_pgn(
            data_page=0, pdu_format=0xDF, pdu_specific=0x04,  # PDU1 = peer-to-peer
            priority=7, src_address=0x01, data=test_data,
            time_limit=0, frame_format=1
        )
        
        assert result is True
        buffer = list(j1939_22._snd_buffer.values())[0]
        
        assert buffer['num_segments'] == 3
        assert all(len(chunk) == 60 for chunk in buffer['data'])
        
        reconstructed = []
        for chunk in buffer['data']:
            reconstructed.extend(chunk)
        assert reconstructed == test_data
    
    @pytest.mark.parametrize("data_length,expected_segments", [
        (61, 2),
        (120, 2),
        (121, 3),
        (180, 3),
        (240, 4),
        (500, 9),
    ])
    def test_various_data_sizes(self, feeder, data_length, expected_segments):
        """Parametrized test for segment count across various data sizes."""
        feeder.accept_all_messages()
        j1939_22 = self.create_j1939_22()
        
        test_data = [i % 256 for i in range(data_length)]
        
        result = j1939_22.send_pgn(
            data_page=0, pdu_format=0xFE, pdu_specific=0xFF,
            priority=7, src_address=0x01, data=test_data,
            time_limit=0, frame_format=FrameFormat.CEFF
        )
        
        assert result is True
        buffer = list(j1939_22._snd_buffer.values())[0]
        
        assert buffer['num_segments'] == expected_segments
        assert len(buffer['data']) == expected_segments
