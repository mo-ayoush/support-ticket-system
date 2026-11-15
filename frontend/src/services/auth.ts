import { Amplify } from 'aws-amplify';
import { fetchAuthSession, getCurrentUser, signInWithRedirect, signOut } from '@aws-amplify/auth';
import { cognitoUserPoolsTokenProvider } from 'aws-amplify/auth/cognito';
import { sessionStorage } from 'aws-amplify/utils';
import { clearOperationRequests } from './operations';

cognitoUserPoolsTokenProvider.setKeyValueStorage(sessionStorage);

const region = import.meta.env.VITE_AWS_REGION as string;
const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID as string;
const clientId = import.meta.env.VITE_COGNITO_CLIENT_ID as string;
const domain = import.meta.env.VITE_COGNITO_DOMAIN as string;
const apiScope = import.meta.env.VITE_COGNITO_API_SCOPE as string;
const redirectSignIn = import.meta.env.VITE_AUTH_REDIRECT_SIGN_IN as string;
const redirectSignOut = import.meta.env.VITE_AUTH_REDIRECT_SIGN_OUT as string;

if (region && userPoolId && clientId && domain && apiScope && redirectSignIn && redirectSignOut) {
  Amplify.configure({ Auth: { Cognito: { userPoolId, userPoolClientId: clientId,
    loginWith: { oauth: { domain, scopes: ['openid', 'email', 'profile', 'aws.cognito.signin.user.admin', apiScope], redirectSignIn: [redirectSignIn], redirectSignOut: [redirectSignOut], responseType: 'code' } } } } });
  console.log('Cognito configuration check:', {
    userPoolConfigured: Boolean(Amplify.getConfig().Auth?.Cognito?.userPoolId),
    clientConfigured: Boolean(Amplify.getConfig().Auth?.Cognito?.userPoolClientId),
  });
}
export interface SessionUser { sub: string; email?: string; groups: string[] }
export async function currentUser(): Promise<SessionUser | null> {
  try {
    const [user, session] = await Promise.all([
      getCurrentUser(),
      fetchAuthSession(),
    ]);
    const payload = session.tokens?.idToken?.payload;
    const groupsClaim = payload?.['cognito:groups'];

    return {
      sub: user.userId,
      email: typeof payload?.email === 'string' ? payload.email : undefined,
      groups: Array.isArray(groupsClaim) ? groupsClaim.map(String) : [],
    };
  } catch {
    return null;
  }
}
export async function accessToken(): Promise<string> {
  const session = await fetchAuthSession();
  const token = session.tokens?.accessToken?.toString();
  if (!token) throw new Error('Your session has expired. Please sign in again.');
  return token;
}
export const login = () => signInWithRedirect();
export async function logout() {
  clearOperationRequests();
  await signOut({ global: false });
}
