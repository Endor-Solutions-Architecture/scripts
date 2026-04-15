import com.nimbusds.jose.jwk.JWK;
class Fixture {
  void run() throws Exception {
    // JWK_PAYLOAD: {"kty":"oct","kid":"Hwizf8zymHFM","alg":"HS256","k":"bUOtgkJoJw9Sb3ANed6S_1LMroxZkBBCbhad4vMj87GjTx-W9t2ky4NHgKeV3MwM"}
    String jwk = "{\"kty\":\"oct\",\"kid\":\"Hwizf8zymHFM\",\"alg\":\"HS256\",\"k\":\"bUOtgkJoJw9Sb3ANed6S_1LMroxZkBBCbhad4vMj87GjTx-W9t2ky4NHgKeV3MwM\"}";
    JWK.parse(jwk);
  }
}
