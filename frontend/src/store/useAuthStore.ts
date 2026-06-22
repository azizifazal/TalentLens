import { create } from "zustand";
import {
  confirmSignUp,
  fetchAuthSession,
  getCurrentUser,
  signIn,
  signOut,
  signUp,
} from "aws-amplify/auth";

interface AuthState {
  isAuthenticated: boolean;
  userEmail: string | null;
  isLoading: boolean;
  error: string | null;
  checkAuth: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  confirmRegistration: (email: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  isAuthenticated: false,
  userEmail: null,
  isLoading: true,
  error: null,

  checkAuth: async () => {
    set({ isLoading: true });
    try {
      const session = await fetchAuthSession();
      const user = await getCurrentUser();
      if (session.tokens) {
        set({
          isAuthenticated: true,
          userEmail: user.signInDetails?.loginId || user.username,
          isLoading: false,
        });
      } else {
        set({ isAuthenticated: false, isLoading: false });
      }
    } catch {
      set({ isAuthenticated: false, isLoading: false });
    }
  },

  login: async (email: string, password: string) => {
    set({ error: null, isLoading: true });
    try {
      const result = await signIn({ username: email, password });
      if (result.isSignedIn) {
        set({ isAuthenticated: true, userEmail: email, isLoading: false });
      } else {
        set({ isLoading: false, error: "Additional verification required." });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Sign in failed";
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  register: async (email: string, password: string) => {
    set({ error: null, isLoading: true });
    try {
      await signUp({
        username: email,
        password,
        options: { userAttributes: { email } },
      });
      set({ isLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Registration failed";
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  confirmRegistration: async (email: string, code: string) => {
    set({ error: null, isLoading: true });
    try {
      await confirmSignUp({ username: email, confirmationCode: code });
      set({ isLoading: false });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Confirmation failed";
      set({ error: message, isLoading: false });
      throw err;
    }
  },

  logout: async () => {
    await signOut();
    set({ isAuthenticated: false, userEmail: null });
  },

  clearError: () => set({ error: null }),
}));
