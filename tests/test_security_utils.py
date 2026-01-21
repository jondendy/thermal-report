"""
Unit tests for security utilities.
Tests path validation, tenant ID validation, and path traversal prevention.
"""
import pytest
from pathlib import Path
from security_utils import (
    validate_tenant_id, validate_batch_id, safe_batch_path, safe_upload_path
)


class TestTenantIdValidation:
    """Test tenant ID validation."""
    
    def test_valid_tenant_id(self):
        """Valid tenant IDs should pass."""
        assert validate_tenant_id('default')
        assert validate_tenant_id('tenant-1')
        assert validate_tenant_id('tenant_2')
        assert validate_tenant_id('TENANT')
    
    def test_invalid_tenant_id_special_chars(self):
        """Reject tenant IDs with special characters."""
        with pytest.raises(ValueError):
            validate_tenant_id('tenant@1')
        with pytest.raises(ValueError):
            validate_tenant_id('tenant.1')
        with pytest.raises(ValueError):
            validate_tenant_id('tenant 1')
    
    def test_invalid_tenant_id_empty(self):
        """Reject empty tenant IDs."""
        with pytest.raises(ValueError):
            validate_tenant_id('')
        with pytest.raises(ValueError):
            validate_tenant_id(None)


class TestBatchIdValidation:
    """Test batch ID validation."""
    
    def test_valid_batch_id(self):
        """Valid batch IDs should pass."""
        assert validate_batch_id('batch_20251214_154632_a1b2c3d4')
        assert validate_batch_id('batch_20240101_000000_00000000')
    
    def test_invalid_batch_id_format(self):
        """Reject invalid batch ID formats."""
        with pytest.raises(ValueError):
            validate_batch_id('batch_invalid')
        with pytest.raises(ValueError):
            validate_batch_id('20251214_154632_a1b2c3d4')
        with pytest.raises(ValueError):
            validate_batch_id('batch_2025_1214_154632_a1b2c3d4')
    
    def test_invalid_batch_id_empty(self):
        """Reject empty batch IDs."""
        with pytest.raises(ValueError):
            validate_batch_id('')
        with pytest.raises(ValueError):
            validate_batch_id(None)


class TestSafeBatchPath:
    """Test safe batch path construction."""
    
    def test_valid_batch_path(self, tmp_path):
        """Valid inputs should construct safe path."""
        path = safe_batch_path(
            'batch_20251214_154632_a1b2c3d4',
            tenant_id='default',
            reports_dir=str(tmp_path)
        )
        
        assert 'batch_20251214_154632_a1b2c3d4' in str(path)
        assert 'default' in str(path)
    
    def test_path_traversal_protection(self, tmp_path):
        """Reject path traversal attempts."""
        # Batch ID with path traversal attempt
        with pytest.raises(ValueError):
            safe_batch_path(
                'batch_20251214_154632_a1b2c3d4/../etc',
                tenant_id='default',
                reports_dir=str(tmp_path)
            )
    
    def test_invalid_batch_id_rejected(self, tmp_path):
        """Invalid batch ID should raise ValueError."""
        with pytest.raises(ValueError):
            safe_batch_path(
                'invalid_batch_id',
                tenant_id='default',
                reports_dir=str(tmp_path)
            )
    
    def test_default_tenant_used(self, tmp_path, monkeypatch):
        """Should use DEFAULT_TENANT if not provided."""
        import settings
        monkeypatch.setattr(settings, 'DEFAULT_TENANT', 'default')
        
        path = safe_batch_path(
            'batch_20251214_154632_a1b2c3d4',
            reports_dir=str(tmp_path)
        )
        
        assert 'default' in str(path)


class TestSafeUploadPath:
    """Test safe upload path construction."""
    
    def test_valid_upload_path(self, tmp_path):
        """Valid inputs should construct safe upload path."""
        path = safe_upload_path(
            tenant_id='default',
            upload_dir=str(tmp_path)
        )
        
        assert 'default' in str(path)
        assert 'batches' in str(path)
    
    def test_invalid_tenant_rejected(self, tmp_path):
        """Invalid tenant ID should raise ValueError."""
        with pytest.raises(ValueError):
            safe_upload_path(
                tenant_id='tenant@invalid',
                upload_dir=str(tmp_path)
            )
