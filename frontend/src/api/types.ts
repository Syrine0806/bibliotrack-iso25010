export type Role = "ADMIN" | "BIBLIOTHECAIRE" | "ADHERENT";
export type CopyStatus = "DISPONIBLE" | "EMPRUNTE" | "RESERVE" | "EN_REPARATION" | "RETIRE";
export type LoanStatus = "EN_COURS" | "EN_RETARD" | "RENDU" | "PERDU";
export type ReservationStatus = "EN_ATTENTE" | "DISPONIBLE" | "HONOREE" | "ANNULEE" | "EXPIREE";
export type PenaltyStatus = "IMPAYEE" | "PAYEE" | "ANNULEE";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface Token {
  access_token: string;
  token_type: string;
  role: Role;
  full_name: string;
}

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  locked_until: string | null;
  created_at: string;
}

export interface Category {
  id: number;
  name: string;
  description: string | null;
}

export interface Author {
  id: number;
  full_name: string;
  nationality: string | null;
  birth_year: number | null;
}

export interface Book {
  id: number;
  isbn: string;
  title: string;
  publisher: string | null;
  publication_year: number | null;
  summary: string | null;
  category: Category;
  authors: Author[];
  total_copies: number;
  available_copies: number;
}

export interface Copy {
  id: number;
  book_id: number;
  barcode: string;
  status: CopyStatus;
  shelf_location: string | null;
  acquired_on: string;
}

interface BookBrief {
  id: number;
  isbn: string;
  title: string;
}

interface UserBrief {
  id: number;
  email: string;
  full_name: string;
}

export interface Loan {
  id: number;
  status: LoanStatus;
  loaned_at: string;
  due_date: string;
  returned_at: string | null;
  renewals_count: number;
  item: { id: number; barcode: string; book: BookBrief };
  user: UserBrief;
}

export interface ReturnResult {
  loan: Loan;
  penalty_amount: string;
  days_late: number;
  reserved_for_user_id: number | null;
}

export interface Reservation {
  id: number;
  status: ReservationStatus;
  created_at: string;
  available_until: string | null;
  book: BookBrief;
  user: UserBrief;
  copy_id: number | null;
  queue_position: number | null;
}

export interface Penalty {
  id: number;
  kind: string;
  amount: string;
  reason: string;
  status: PenaltyStatus;
  created_at: string;
  settled_at: string | null;
  loan_id: number | null;
  user: UserBrief;
}

export interface AuditEntry {
  id: number;
  timestamp: string;
  user_id: number | null;
  user_email: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  details: string | null;
  ip_address: string | null;
}

export interface CountItem {
  label: string;
  value: number;
}

export interface Dashboard {
  total_books: number;
  total_copies: number;
  available_copies: number;
  active_loans: number;
  overdue_loans: number;
  active_members: number;
  pending_reservations: number;
  unpaid_penalties_total: string;
  loans_in_period: number;
  loans_by_month: CountItem[];
  top_books: CountItem[];
  loans_by_category: CountItem[];
  copies_by_status: CountItem[];
}

export interface IsbnLookup {
  isbn: string;
  found: boolean;
  source: string;
  title: string | null;
  publisher: string | null;
  publication_year: number | null;
  authors: string[];
  message: string | null;
}
