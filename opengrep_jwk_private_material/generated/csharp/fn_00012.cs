using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"x0k3zdp8fFtd","alg":"RS256","n":"q_7gFXQjzPaQCUABHJMtGMLn2RCZKU8Z5O6GHncJ90-e14lE","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"x0k3zdp8fFtd\",\"alg\":\"RS256\",\"n\":\"q_7gFXQjzPaQCUABHJMtGMLn2RCZKU8Z5O6GHncJ90-e14lE\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}
