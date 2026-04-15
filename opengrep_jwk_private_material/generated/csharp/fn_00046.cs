using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"JfijzjuIkbKE","alg":"RS256","n":"sOGqBdRst2NY7lxEuQCTEq-pTgshidPJhMmfj9PEsJsW3G5c","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"JfijzjuIkbKE\",\"alg\":\"RS256\",\"n\":\"sOGqBdRst2NY7lxEuQCTEq-pTgshidPJhMmfj9PEsJsW3G5c\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
