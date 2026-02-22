import 'next-auth';

declare module 'next-auth' {
  interface Session {
    user: {
      id: string;
      email: string;
      organizationId: string;
    };
  }

  interface User {
    organizationId: string;
  }
}

declare module 'next-auth/jwt' {
  interface JWT {
    organizationId: string;
  }
}
