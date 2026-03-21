import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import SettingsAccount from '../SettingsAccount';

describe('SettingsAccount', () => {
  const mockOnLogout = vi.fn();
  const mockUser = { email: 'test@example.com' };

  beforeEach(() => {
    vi.clearAllMocks();
    // Reset fetch mock
    vi.restoreAllMocks();
  });

  it('shows "계정 비활성화" (not "영구 삭제")', () => {
    render(<SettingsAccount user={mockUser} onLogout={mockOnLogout} />);

    // Click "계정 삭제" to open confirm flow
    fireEvent.click(screen.getByText('계정 삭제'));

    // Should show "계정 비활성화" button (not "영구 삭제")
    expect(screen.getByText('계정 비활성화')).toBeInTheDocument();
    expect(screen.queryByText('영구 삭제')).not.toBeInTheDocument();
  });

  it('shows "비활성화" description (not "영구적으로 삭제")', () => {
    render(<SettingsAccount user={mockUser} onLogout={mockOnLogout} />);

    // Click to open confirm
    fireEvent.click(screen.getByText('계정 삭제'));

    // Description text mentions deactivation
    expect(screen.getByText(/계정을 비활성화하면/)).toBeInTheDocument();
    expect(screen.getByText(/30일간 보관 후 영구 삭제/)).toBeInTheDocument();
  });

  it('delete button disabled when email does not match', () => {
    render(<SettingsAccount user={mockUser} onLogout={mockOnLogout} />);

    // Open confirm
    fireEvent.click(screen.getByText('계정 삭제'));

    const confirmButton = screen.getByText('계정 비활성화').closest('button')!;

    // Initially disabled (empty input)
    expect(confirmButton).toBeDisabled();

    // Wrong email — still disabled
    const input = screen.getByPlaceholderText('test@example.com');
    fireEvent.change(input, { target: { value: 'wrong@email.com' } });
    expect(confirmButton).toBeDisabled();
  });

  it('delete button enabled when email matches', () => {
    render(<SettingsAccount user={mockUser} onLogout={mockOnLogout} />);

    // Open confirm
    fireEvent.click(screen.getByText('계정 삭제'));

    const input = screen.getByPlaceholderText('test@example.com');
    fireEvent.change(input, { target: { value: 'test@example.com' } });

    const confirmButton = screen.getByText('계정 비활성화').closest('button')!;
    expect(confirmButton).not.toBeDisabled();
  });

  it('calls DELETE /api/studio/account on confirm', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'deactivated' }),
    });
    vi.stubGlobal('fetch', mockFetch);

    render(<SettingsAccount user={mockUser} onLogout={mockOnLogout} />);

    // Open confirm
    fireEvent.click(screen.getByText('계정 삭제'));

    // Type matching email
    const input = screen.getByPlaceholderText('test@example.com');
    fireEvent.change(input, { target: { value: 'test@example.com' } });

    // Click confirm button
    fireEvent.click(screen.getByText('계정 비활성화'));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/studio/account'),
        expect.objectContaining({
          method: 'DELETE',
          credentials: 'include',
        }),
      );
    });

    // Should show success message
    expect(await screen.findByText('계정이 비활성화되었습니다. 잠시 후 로그아웃됩니다.')).toBeInTheDocument();

    vi.unstubAllGlobals();
  });
});
