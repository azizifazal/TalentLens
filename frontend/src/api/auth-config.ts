import { Amplify } from "aws-amplify";

const userPoolId: string = import.meta.env.VITE_COGNITO_USER_POOL_ID || "";
const userPoolClientId: string = import.meta.env.VITE_COGNITO_CLIENT_ID || "";

export function configureAuth(): void {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
        signUpVerificationMethod: "code",
        loginWith: {
          email: true,
        },
      },
    },
  });
}
